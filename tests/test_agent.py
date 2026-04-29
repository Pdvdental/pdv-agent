from unittest.mock import patch, MagicMock, call
import pytest

from app.agent.tools import dispatch, tool_escalate_to_human


@patch("app.agent.tools.db")
@patch("app.agent.tools.chatwoot")
def test_escalate_to_human_calls_chatwoot(mock_chatwoot, mock_db):
    mock_db.save_escalation.return_value = {}
    mock_db.update_conversation_status.return_value = None
    mock_chatwoot.add_private_note.return_value = {}
    mock_chatwoot.add_label.return_value = {}
    mock_chatwoot.update_conversation_status.return_value = {}

    result = tool_escalate_to_human(
        reason="urgencia",
        summary="Paciente con dolor agudo",
        conversation_id=42,
        db_conversation_id="uuid-test",
    )

    mock_db.save_escalation.assert_called_once_with("uuid-test", "urgencia")
    mock_db.update_conversation_status.assert_called_once_with("uuid-test", "escalated")
    mock_chatwoot.add_private_note.assert_called_once()
    mock_chatwoot.add_label.assert_called_once_with(42, ["escalado"])
    mock_chatwoot.update_conversation_status.assert_called_once_with(42, "pending")
    assert "equipo" in result


@patch("app.agent.tools.db")
@patch("app.agent.tools.cal")
def test_dispatch_lookup_faq(mock_cal, mock_db):
    mock_db.search_faqs.return_value = [
        {"question": "¿Cuánto cuesta la limpieza?", "answer": "60-90 €"}
    ]
    result = dispatch("lookup_faq", {"query": "limpieza precio"})
    assert "limpieza" in result.lower()


def test_dispatch_unknown_tool():
    result = dispatch("nonexistent_tool", {})
    assert "no encontrada" in result


@patch("app.agent.tools.db")
@patch("app.agent.tools.cal")
def test_dispatch_check_availability(mock_cal, mock_db):
    mock_cal.check_availability.return_value = [
        {"starts_at": "2026-05-05T10:00:00+02:00", "ends_at": "2026-05-05T10:30:00+02:00", "label": "5 may, 10:00"}
    ]
    result = dispatch("check_availability", {
        "date_from": "2026-05-05T00:00:00+02:00",
        "date_to": "2026-05-05T23:59:59+02:00",
    })
    assert "5 may" in result