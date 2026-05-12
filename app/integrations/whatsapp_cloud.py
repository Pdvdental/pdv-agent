import logging
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _base_url() -> str:
    s = get_settings()
    return f"https://graph.facebook.com/{s.meta_graph_api_version}/{s.meta_phone_number_id}/messages"


def _headers() -> dict:
    s = get_settings()
    return {
        "Authorization": f"Bearer {s.meta_graph_token}",
        "Content-Type": "application/json",
    }


def send_text(to: str, body: str) -> dict:
    """
    Send a free-form text message via WhatsApp Cloud API.

    `to` should be the wa_id (E.164 without leading +, exactly what Meta sends in `from`).
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    to_clean = to.lstrip("+")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_clean,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    resp = httpx.post(_base_url(), headers=_headers(), json=payload, timeout=20)
    if resp.status_code >= 400:
        logger.error("WA-CLOUD send failed status=%s body=%s", resp.status_code, resp.text[:500])
    resp.raise_for_status()
    return resp.json()
