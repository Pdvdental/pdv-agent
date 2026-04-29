import logging
from fastapi import Request, HTTPException

from app.config import get_settings
from app.integrations.chatwoot import validate_webhook_signature

logger = logging.getLogger(__name__)


async def verify_chatwoot_webhook(request: Request) -> dict:
    """Validates HMAC signature and parses the Chatwoot webhook payload."""
    body = await request.body()
    signature = request.headers.get("X-Chatwoot-Signature", "")

    if not validate_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return await request.json()


def should_bot_respond(conversation: dict) -> bool:
    s = get_settings()
    if conversation.get("status") != "open":
        return False
    assignee = conversation.get("meta", {}).get("assignee")
    if assignee and assignee.get("id") != s.chatwoot_bot_user_id:
        return False
    labels = [lbl if isinstance(lbl, str) else lbl.get("title", "") for lbl in conversation.get("labels", [])]
    if "no_bot" in labels:
        return False
    return True


def extract_message_data(payload: dict) -> dict | None:
    """
    Returns relevant fields from a Chatwoot webhook payload, or None if the
    event should be ignored.
    """
    event = payload.get("event")

    if event == "message_created":
        msg_type = payload.get("message_type")
        if msg_type != "incoming":
            return None

        conversation = payload.get("conversation", {})
        sender = payload.get("sender", {})
        content = payload.get("content", "").strip()

        if not content:
            return None

        return {
            "chatwoot_conversation_id": conversation.get("id"),
            "chatwoot_message_id": payload.get("id"),
            "conversation": conversation,
            "phone": sender.get("phone_number") or sender.get("identifier", ""),
            "sender_name": sender.get("name", ""),
            "chatwoot_contact_id": sender.get("id"),
            "content": content,
        }

    if event == "conversation_status_changed":
        # Bot does not act on status changes, just logs
        logger.info(f"Conversation status changed: {payload.get('conversation', {}).get('id')} → {payload.get('status')}")
        return None

    return None