import asyncio
import logging

from app.integrations import db
from app.integrations import chatwoot
from app.agent.gemini_client import chat_turn
from app.handlers.webhook import should_bot_respond

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30


async def handle_incoming_message(data: dict) -> None:
    """
    Orchestrates a full conversation turn:
    1. Upsert patient
    2. Get/create conversation
    3. Check if bot should respond
    4. Call Gemini (with timeout)
    5. Send response via Chatwoot
    """
    phone = data["phone"]
    content = data["content"]
    chatwoot_conversation_id = data["chatwoot_conversation_id"]
    chatwoot_contact_id = data["chatwoot_contact_id"]
    sender_name = data["sender_name"]
    conversation_payload = data["conversation"]

    if not should_bot_respond(conversation_payload):
        logger.info(f"Bot muted for conversation {chatwoot_conversation_id}")
        return

    # Move pending conversations to open so the bot response reaches the user
    if conversation_payload.get("status") == "pending":
        chatwoot.update_conversation_status(chatwoot_conversation_id, "open")

    # Upsert patient
    patient = db.upsert_patient(
        phone_e164=phone,
        full_name=sender_name or None,
        chatwoot_contact_id=chatwoot_contact_id,
    )

    # Get or create DB conversation
    db_conversation = db.get_or_create_conversation(patient["id"], chatwoot_conversation_id)
    db_conversation_id = db_conversation["id"]

    try:
        response_text = await asyncio.wait_for(
            asyncio.to_thread(
                chat_turn,
                db_conversation_id,
                chatwoot_conversation_id,
                content,
            ),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout on conversation {chatwoot_conversation_id}")
        response_text = (
            "Lo siento, estoy tardando más de lo normal. "
            "Por favor, vuelve a intentarlo en un momento o llama al 93 729 4880."
        )
        chatwoot.escalate_to_human if False else None  # noqa — don't auto-escalate timeouts

    chatwoot.send_message(chatwoot_conversation_id, response_text)