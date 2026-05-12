import asyncio
import logging

from app.config import get_settings
from app.integrations import db
from app.integrations import chatwoot
from app.integrations import whatsapp_cloud as wa
from app.agent.gemini_client import chat_turn

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 90
CW_LOOKUP_RETRIES = 6
CW_LOOKUP_BACKOFF_S = 0.5


async def process_meta_payload(payload: dict) -> None:
    """Top-level entry: walk every message in a Meta webhook payload."""
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for msg in value.get("messages", []) or []:
                try:
                    await _handle_one(msg, value)
                except Exception:
                    logger.exception("META-DIRECT: unhandled error wamid=%s", msg.get("id"))


async def _handle_one(msg: dict, value: dict) -> None:
    s = get_settings()

    wamid = msg.get("id")
    wa_from = msg.get("from")  # E.164 without leading +
    msg_type = msg.get("type")

    if not wamid or not wa_from:
        return

    phone_e164 = "+" + wa_from

    # Dedup
    if await asyncio.to_thread(db.message_exists_by_source_id, wamid):
        logger.info("META-DIRECT: duplicate wamid=%s, skipping", wamid)
        return

    # Only text supported for now
    if msg_type != "text":
        logger.info("META-DIRECT: skipping non-text type=%s wamid=%s", msg_type, wamid)
        return

    text_body = (msg.get("text") or {}).get("body", "").strip()
    if not text_body:
        return

    # Extract sender name from contacts[]
    sender_name = None
    for c in value.get("contacts", []) or []:
        if c.get("wa_id") == wa_from:
            sender_name = (c.get("profile") or {}).get("name")
            break

    # Find Chatwoot conv (give the proxy forward a moment to land first)
    cw_conv_id = await _find_cw_conv_with_retry(phone_e164)

    # Honor Chatwoot-side mute (Option A: assign to human OR add 'no_bot' label)
    if cw_conv_id:
        try:
            cw_conv = await asyncio.to_thread(chatwoot.get_conversation, cw_conv_id)
        except Exception:
            cw_conv = None
            logger.exception("META-DIRECT: get_conversation failed conv=%s", cw_conv_id)
        if cw_conv and not _should_bot_respond_cw(cw_conv, s):
            logger.info("META-DIRECT: muted by Chatwoot state conv=%s", cw_conv_id)
            return
    else:
        logger.warning("META-DIRECT: no Chatwoot conv found for %s after retries — bot will reply anyway", phone_e164)

    # Persist patient + DB conv
    patient = await asyncio.to_thread(db.upsert_patient, phone_e164, sender_name, None)
    cw_id_for_db = cw_conv_id or 0
    db_conv = await asyncio.to_thread(db.get_or_create_conversation, patient["id"], cw_id_for_db)
    db_conv_id = db_conv["id"]

    # Run agent (90s budget, off the event loop)
    try:
        reply = await asyncio.wait_for(
            asyncio.to_thread(chat_turn, db_conv_id, cw_id_for_db, text_body, wamid, patient.get("full_name")),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("META-DIRECT: chat_turn timeout wamid=%s", wamid)
        reply = (
            "Lo siento, estoy tardando más de lo normal. "
            "Vuelve a intentarlo o llama al 93 729 4880."
        )

    # Send via Cloud API
    try:
        await asyncio.to_thread(wa.send_text, wa_from, reply)
        logger.info("META-DIRECT: replied to %s (wamid=%s)", phone_e164, wamid)
    except Exception:
        logger.exception("META-DIRECT: Cloud API send failed to %s", phone_e164)

    # Mirror to Chatwoot as private note (best effort)
    if cw_conv_id is None:
        cw_conv_id = await _find_cw_conv_with_retry(phone_e164, retries=3)
    if cw_conv_id:
        try:
            await asyncio.to_thread(chatwoot.add_private_note, cw_conv_id, f"🤖 Bot reply:\n{reply}")
        except Exception:
            logger.exception("META-DIRECT: mirror to Chatwoot failed conv=%s", cw_conv_id)


async def _find_cw_conv_with_retry(phone_e164: str, retries: int = CW_LOOKUP_RETRIES) -> int | None:
    for attempt in range(retries):
        try:
            conv_id = await asyncio.to_thread(chatwoot.find_open_conversation_for_phone, phone_e164)
        except Exception:
            logger.exception("META-DIRECT: chatwoot lookup error attempt=%d", attempt)
            conv_id = None
        if conv_id:
            return conv_id
        await asyncio.sleep(CW_LOOKUP_BACKOFF_S)
    return None


def _should_bot_respond_cw(cw_conv: dict, s) -> bool:
    status = cw_conv.get("status")
    if status == "resolved":
        return False
    assignee = (cw_conv.get("meta") or {}).get("assignee")
    if assignee and assignee.get("id") != s.chatwoot_bot_user_id:
        return False
    labels = cw_conv.get("labels") or []
    label_names = [l if isinstance(l, str) else l.get("title", "") for l in labels]
    if "no_bot" in label_names:
        return False
    return True
