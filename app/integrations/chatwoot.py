import hashlib
import hmac
import httpx
from app.config import get_settings


def _headers() -> dict:
    return {"api_access_token": get_settings().chatwoot_api_access_token}


def _bot_headers() -> dict:
    # Use the agent bot token so Chatwoot attributes the message to the bot,
    # not to the human admin. Using the admin token causes Chatwoot to auto-assign
    # the conversation to the admin and stop calling the bot webhook.
    return {"api_access_token": get_settings().chatwoot_hmac_token}


def _base() -> str:
    s = get_settings()
    return f"{s.chatwoot_base_url}/api/v1/accounts/{s.chatwoot_account_id}"


def send_message(conversation_id: int, content: str) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/messages"
    resp = httpx.post(
        url,
        headers=_bot_headers(),
        json={"content": content, "message_type": "outgoing", "private": False},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def send_template(contact_id: int, template_name: str, parameters: list[str]) -> dict:
    s = get_settings()
    processed = {str(i + 1): v for i, v in enumerate(parameters)}
    resp = httpx.post(
        f"{_base()}/conversations",
        headers=_headers(),
        json={
            "inbox_id": s.chatwoot_inbox_id,
            "contact_id": contact_id,
            "message": {
                "content": parameters[0] if parameters else "",
                "template_params": {
                    "name": template_name,
                    "category": "UTILITY",
                    "language": "es_MX",
                    "processed_params": processed,
                },
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def add_private_note(conversation_id: int, content: str) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/messages"
    resp = httpx.post(
        url,
        headers=_headers(),
        json={"content": content, "message_type": "outgoing", "private": True},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def assign_conversation(conversation_id: int, assignee_id: int | None) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/assignments"
    resp = httpx.post(
        url,
        headers=_headers(),
        json={"assignee_id": assignee_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def update_conversation_status(conversation_id: int, status: str) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/toggle_status"
    resp = httpx.post(
        url,
        headers=_headers(),
        json={"status": status},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def add_label(conversation_id: int, labels: list[str]) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/labels"
    resp = httpx.post(
        url,
        headers=_headers(),
        json={"labels": labels},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def validate_webhook_signature(payload: bytes, signature_header: str) -> bool:
    token = get_settings().chatwoot_hmac_token
    expected = hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def get_conversation(conversation_id: int) -> dict | None:
    url = f"{_base()}/conversations/{conversation_id}"
    resp = httpx.get(url, headers=_headers(), timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def find_open_conversation_for_phone(phone_e164: str) -> int | None:
    """
    Returns the most recent open/pending Chatwoot conversation ID in our inbox
    for a contact identified by phone (E.164 with leading +). None if not found.
    """
    s = get_settings()
    search_q = phone_e164.lstrip("+")
    resp = httpx.get(
        f"{_base()}/contacts/search",
        headers=_headers(),
        params={"q": search_q, "include": "contact_inboxes"},
        timeout=10,
    )
    resp.raise_for_status()
    contacts = resp.json().get("payload", []) or []
    if not contacts:
        return None

    candidate_convs = []
    for contact in contacts:
        cid = contact.get("id")
        if not cid:
            continue
        cresp = httpx.get(
            f"{_base()}/contacts/{cid}/conversations",
            headers=_headers(),
            timeout=10,
        )
        if cresp.status_code != 200:
            continue
        payload = cresp.json().get("payload", []) or []
        for conv in payload:
            if conv.get("inbox_id") != s.chatwoot_inbox_id:
                continue
            if conv.get("status") in ("open", "pending"):
                candidate_convs.append(conv)

    if not candidate_convs:
        return None

    candidate_convs.sort(key=lambda c: c.get("last_activity_at") or 0, reverse=True)
    return candidate_convs[0].get("id")