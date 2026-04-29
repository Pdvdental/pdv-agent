import hashlib
import hmac
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.handlers.webhook import should_bot_respond, extract_message_data

client = TestClient(app)

MOCK_SETTINGS = MagicMock(
    chatwoot_hmac_token="test-secret",
    chatwoot_bot_user_id=99,
    internal_api_token="internal-secret",
    log_level="INFO",
)


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


@patch("app.handlers.webhook.get_settings", return_value=MOCK_SETTINGS)
def test_valid_signature_accepted(mock_settings):
    payload = json.dumps({"event": "message_created", "message_type": "outgoing"}).encode()
    sig = _sign(payload, "test-secret")

    with patch("app.main.verify_chatwoot_webhook") as mock_verify:
        mock_verify.return_value = {"event": "message_created", "message_type": "outgoing"}
        resp = client.post(
            "/webhook/chatwoot",
            content=payload,
            headers={"X-Chatwoot-Signature": sig, "Content-Type": "application/json"},
        )
    assert resp.status_code == 200


def test_should_bot_respond_open_unassigned():
    conv = {"status": "open", "meta": {}, "labels": []}
    with patch("app.handlers.webhook.get_settings", return_value=MOCK_SETTINGS):
        assert should_bot_respond(conv) is True


def test_should_bot_respond_pending():
    conv = {"status": "pending", "meta": {}, "labels": []}
    with patch("app.handlers.webhook.get_settings", return_value=MOCK_SETTINGS):
        assert should_bot_respond(conv) is False


def test_should_bot_respond_assigned_to_human():
    conv = {"status": "open", "meta": {"assignee": {"id": 5}}, "labels": []}
    with patch("app.handlers.webhook.get_settings", return_value=MOCK_SETTINGS):
        assert should_bot_respond(conv) is False


def test_should_bot_respond_no_bot_label():
    conv = {"status": "open", "meta": {}, "labels": ["no_bot"]}
    with patch("app.handlers.webhook.get_settings", return_value=MOCK_SETTINGS):
        assert should_bot_respond(conv) is False


def test_extract_message_data_incoming():
    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "id": 123,
        "content": "Hola, quiero cita",
        "conversation": {"id": 42, "status": "open", "meta": {}, "labels": []},
        "sender": {"id": 7, "name": "Juan", "phone_number": "+34600000000"},
    }
    data = extract_message_data(payload)
    assert data is not None
    assert data["content"] == "Hola, quiero cita"
    assert data["phone"] == "+34600000000"
    assert data["chatwoot_conversation_id"] == 42


def test_extract_message_data_outgoing_ignored():
    payload = {
        "event": "message_created",
        "message_type": "outgoing",
        "content": "Respuesta del bot",
        "conversation": {"id": 42},
        "sender": {},
    }
    assert extract_message_data(payload) is None


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch("app.main.get_settings", return_value=MOCK_SETTINGS)
def test_internal_reminders_wrong_token(mock_settings):
    resp = client.post(
        "/internal/run-reminders",
        headers={"X-Internal-Token": "wrong"},
    )
    assert resp.status_code == 403