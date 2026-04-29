import json
from datetime import datetime, timedelta
import pytz

from app.config import get_settings
from app.integrations import calendar as cal
from app.integrations import db
from app.integrations import chatwoot

# ---------------------------------------------------------------------------
# Gemini FunctionDeclaration schemas
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "check_availability",
        "description": "Consulta los huecos disponibles en el calendario de la clínica entre dos fechas.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Fecha/hora de inicio de búsqueda en formato ISO 8601. Ej: 2024-11-12T00:00:00",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha/hora de fin de búsqueda en formato ISO 8601. Ej: 2024-11-15T23:59:59",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duración de la cita en minutos. Por defecto 30.",
                },
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Reserva una cita en el calendario para un paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Nombre completo del paciente."},
                "patient_phone": {"type": "string", "description": "Teléfono del paciente en formato E.164."},
                "service": {"type": "string", "description": "Tipo de servicio (limpieza, revisión, implante, ortodoncia, urgencia, etc.)."},
                "starts_at": {"type": "string", "description": "Fecha y hora de inicio en ISO 8601."},
                "notes": {"type": "string", "description": "Notas adicionales (opcional)."},
            },
            "required": ["patient_name", "patient_phone", "service", "starts_at"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Cambia la fecha/hora de la próxima cita confirmada de un paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {"type": "string", "description": "Teléfono del paciente en E.164."},
                "new_starts_at": {"type": "string", "description": "Nueva fecha y hora en ISO 8601."},
            },
            "required": ["patient_phone", "new_starts_at"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancela la próxima cita confirmada de un paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {"type": "string", "description": "Teléfono del paciente en E.164."},
            },
            "required": ["patient_phone"],
        },
    },
    {
        "name": "lookup_faq",
        "description": "Busca respuestas a preguntas frecuentes sobre la clínica (precios, servicios, horarios, ubicación, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Pregunta o palabras clave del paciente."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escala la conversación a un miembro humano del equipo cuando el bot no puede resolver la situación.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Motivo de escalación (urgencia, queja, confusión persistente, etc.)."},
                "summary": {"type": "string", "description": "Resumen breve de la conversación para que el equipo entienda el contexto."},
                "conversation_id": {"type": "integer", "description": "ID de la conversación en Chatwoot."},
                "db_conversation_id": {"type": "string", "description": "UUID de la conversación en Supabase."},
            },
            "required": ["reason", "summary", "conversation_id", "db_conversation_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _slot_duration() -> int:
    return get_settings().slot_duration_minutes


def tool_check_availability(date_from: str, date_to: str, duration_minutes: int = None) -> str:
    slots = cal.check_availability(date_from, date_to, duration_minutes or _slot_duration())
    if not slots:
        return "No hay huecos disponibles en ese rango de fechas. Prueba un rango más amplio."
    lines = "\n".join(f"• {s['label']} (starts_at: {s['starts_at']})" for s in slots)
    return f"Huecos disponibles:\n{lines}"


def tool_book_appointment(
    patient_name: str,
    patient_phone: str,
    service: str,
    starts_at: str,
    notes: str = None,
) -> str:
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    dt_start = datetime.fromisoformat(starts_at).astimezone(tz)
    dt_end = dt_start + timedelta(minutes=s.slot_duration_minutes)

    summary = f"{patient_name} - {service}"
    event = cal.create_event(
        summary=summary,
        starts_at=dt_start.isoformat(),
        ends_at=dt_end.isoformat(),
        description=notes,
    )

    patient = db.upsert_patient(patient_phone, patient_name)
    db.save_appointment(
        patient_id=patient["id"],
        google_event_id=event["id"],
        starts_at=dt_start.isoformat(),
        ends_at=dt_end.isoformat(),
        service=service,
    )

    label = dt_start.strftime("%-d %b a las %H:%M")
    return f"Cita confirmada ✅\n• Paciente: {patient_name}\n• Servicio: {service}\n• Fecha: {label}"


def tool_reschedule_appointment(patient_phone: str, new_starts_at: str) -> str:
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    appt = db.get_next_appointment_by_phone(patient_phone)
    if not appt:
        return "No encontré ninguna cita confirmada próxima para ese número."

    dt_start = datetime.fromisoformat(new_starts_at).astimezone(tz)
    dt_end = dt_start + timedelta(minutes=s.slot_duration_minutes)

    cal.update_event(appt["google_event_id"], dt_start.isoformat(), dt_end.isoformat())
    db.update_appointment(appt["id"], starts_at=dt_start.isoformat(), ends_at=dt_end.isoformat())

    label = dt_start.strftime("%-d %b a las %H:%M")
    return f"Cita reagendada ✅\nNueva fecha: {label}"


def tool_cancel_appointment(patient_phone: str) -> str:
    appt = db.get_next_appointment_by_phone(patient_phone)
    if not appt:
        return "No encontré ninguna cita confirmada próxima para ese número."

    cal.delete_event(appt["google_event_id"])
    db.update_appointment(appt["id"], status="cancelled")
    return "Cita cancelada ✅. Si quieres otra, dímelo y buscamos un hueco."


def tool_lookup_faq(query: str) -> str:
    faqs = db.search_faqs(query)
    if not faqs:
        return "No encontré información sobre eso en nuestra base de datos."
    parts = [f"**{f['question']}**\n{f['answer']}" for f in faqs]
    return "\n\n".join(parts)


def tool_escalate_to_human(
    reason: str,
    summary: str,
    conversation_id: int,
    db_conversation_id: str,
) -> str:
    s = get_settings()

    db.save_escalation(db_conversation_id, reason)
    db.update_conversation_status(db_conversation_id, "escalated")

    chatwoot.add_private_note(
        conversation_id,
        f"🤖 Escalación automática\n**Motivo:** {reason}\n**Resumen:** {summary}",
    )
    chatwoot.add_label(conversation_id, ["escalado"])
    chatwoot.update_conversation_status(conversation_id, "pending")

    return (
        "Te paso con una persona del equipo, te contactarán en breve 😊 "
        "Si es urgente puedes llamar al 93 729 4880."
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "check_availability": tool_check_availability,
    "book_appointment": tool_book_appointment,
    "reschedule_appointment": tool_reschedule_appointment,
    "cancel_appointment": tool_cancel_appointment,
    "lookup_faq": tool_lookup_faq,
    "escalate_to_human": tool_escalate_to_human,
}


def dispatch(tool_name: str, tool_args: dict) -> str:
    fn = TOOL_MAP.get(tool_name)
    if fn is None:
        return f"Tool '{tool_name}' no encontrada."
    try:
        return fn(**tool_args)
    except Exception as e:
        return f"Error ejecutando {tool_name}: {e}"