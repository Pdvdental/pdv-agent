import hashlib
import hmac
import httpx
from app.config import get_settings


def _headers() -> dict:
    return {"api_access_token": get_settings().chatwoot_api_access_token}


def _base() -> str:
    s = get_settings()
    return f"{s.chatwoot_base_url}/api/v1/accounts/{s.chatwoot_account_id}"


def send_message(conversation_id: int, content: str) -> dict:
    url = f"{_base()}/conversations/{conversation_id}/messages"
    resp = httpx.post(
        url,
        headers=_headers(),
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
                    "language": "es",
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