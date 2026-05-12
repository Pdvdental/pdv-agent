from unittest.mock import patch, MagicMock

from app.agent.tools import dispatch, tool_escalate_to_human, _normalize_slug


@patch("app.agent.tools.get_settings")
@patch("app.agent.tools.db")
@patch("app.agent.tools.chatwoot")
def test_escalate_to_human_calls_chatwoot(mock_chatwoot, mock_db, mock_settings):
    mock_settings.return_value = MagicMock(chatwoot_bot_user_id=1)
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
    mock_chatwoot.update_conversation_status.assert_called_once_with(42, "open")
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
def test_dispatch_check_availability_returns_slots(mock_cal, mock_db):
    mock_db.get_doctors_for_service.return_value = [
        {"id": 1, "name": "Laurys", "calendar_id": "cal-1"}
    ]
    mock_cal.check_availability.return_value = [
        {
            "doctor_id": 1,
            "doctor_name": "Laurys",
            "calendar_id": "cal-1",
            "starts_at": "2026-05-05T10:00:00+02:00",
            "ends_at": "2026-05-05T10:30:00+02:00",
            "label": "5 may, 10:00",
        }
    ]
    result = dispatch("check_availability", {
        "date_from": "2026-05-05T00:00:00+02:00",
        "date_to": "2026-05-05T23:59:59+02:00",
        "service": "limpieza",
    })
    assert "5 may" in result
    assert "doctor_id: 1" in result


@patch("app.agent.tools.db")
@patch("app.agent.tools.cal")
def test_dispatch_check_availability_unknown_service_escalates(mock_cal, mock_db):
    result = dispatch("check_availability", {
        "date_from": "2026-05-05T00:00:00+02:00",
        "date_to": "2026-05-05T23:59:59+02:00",
        "service": "implante",
    })
    assert "escalate_to_human" in result
    mock_db.get_doctors_for_service.assert_not_called()
    mock_cal.check_availability.assert_not_called()


@patch("app.agent.tools.db")
@patch("app.agent.tools.cal")
def test_dispatch_check_availability_no_doctor_escalates(mock_cal, mock_db):
    mock_db.get_doctors_for_service.return_value = []
    result = dispatch("check_availability", {
        "date_from": "2026-05-05T00:00:00+02:00",
        "date_to": "2026-05-05T23:59:59+02:00",
        "service": "endodoncia",
    })
    assert "escalate_to_human" in result


def test_normalize_slug_strips_accents_and_case():
    assert _normalize_slug("Revisión") == "revision"
    assert _normalize_slug(" Odontología General ") == "odontologia-general"
    assert _normalize_slug("ENDODONCIA") == "endodoncia"
    assert _normalize_slug("odontologia_general") == "odontologia-general"
