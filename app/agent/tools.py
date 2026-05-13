import logging
import unicodedata
from datetime import datetime, timedelta
import pytz

from app.config import get_settings
from app.integrations import calendar as cal
from app.integrations import db
from app.integrations import chatwoot
from app.integrations import whatsapp_cloud as wa

logger = logging.getLogger(__name__)


VALID_SERVICE_SLUGS = {
    "ortodoncia",
    "odontologia-general",
    "limpieza",
    "revision",
    "caries",
    "endodoncia",
}


def _normalize_slug(s: str) -> str:
    """Lowercase, strip accents, normalize separators. 'Revisión' -> 'revision'."""
    s = s.lower().strip().replace("_", "-").replace(" ", "-")
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    return s

# ---------------------------------------------------------------------------
# Gemini FunctionDeclaration schemas
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "check_availability",
        "description": (
            "Consulta los huecos disponibles en el calendario de la clínica entre dos fechas. "
            "Pasa siempre el parámetro 'service' con el tratamiento que menciona el paciente."
        ),
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
                "service": {
                    "type": "string",
                    "description": (
                        "Tratamiento solicitado. Usa exactamente uno de estos slugs: "
                        "ortodoncia, odontologia-general, limpieza, revision, caries, endodoncia. "
                        "Si no está claro, usa odontologia-general."
                    ),
                },
            },
            "required": ["date_from", "date_to", "service"],
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
                "service": {"type": "string", "description": "Tipo de servicio (slug exacto del check_availability)."},
                "starts_at": {"type": "string", "description": "Fecha y hora de inicio en ISO 8601 (exactamente el starts_at devuelto por check_availability)."},
                "doctor_id": {"type": "integer", "description": "ID del doctor del slot elegido (devuelto por check_availability)."},
                "notes": {"type": "string", "description": "Notas adicionales (opcional)."},
            },
            "required": ["patient_name", "patient_phone", "service", "starts_at", "doctor_id"],
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
                "skip_followup": {"type": "boolean", "description": "true si el paciente dijo que no va a volver o que llamará él mismo. Por defecto false."},
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
        "name": "close_conversation",
        "description": "Cierra la conversación cuando el paciente se despide o indica que no necesita nada más. Llama esta tool ANTES de despedirte.",
        "parameters": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "integer", "description": "ID de la conversación en Chatwoot."},
                "db_conversation_id": {"type": "string", "description": "UUID de la conversación en Supabase."},
            },
            "required": ["conversation_id", "db_conversation_id"],
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

def tool_check_availability(date_from: str, date_to: str, service: str = None) -> str:
    if service:
        slug = _normalize_slug(service)
        if slug not in VALID_SERVICE_SLUGS:
            return (
                "Este tratamiento no es reservable por WhatsApp. "
                "Por favor llama a escalate_to_human para que un humano lo gestione."
            )
        doctors = db.get_doctors_for_service(slug)
    else:
        doctors = db.get_all_active_doctors()

    if not doctors:
        return (
            "Para este tratamiento la gestión es directa con la clínica. "
            "Indica al paciente que puede llamar al 93 729 4880. No es necesario escalar."
        )

    slots = cal.check_availability(doctors, date_from, date_to)
    if not slots:
        return "No hay huecos disponibles en ese rango de fechas. Prueba un rango más amplio."

    multiple_doctors = len(doctors) > 1
    lines = []
    for s in slots:
        doctor_str = f" con {s['doctor_name']}" if multiple_doctors else ""
        lines.append(f"• {s['label']}{doctor_str} (starts_at: {s['starts_at']}, doctor_id: {s['doctor_id']})")
    return f"Huecos disponibles:\n" + "\n".join(lines)


def tool_book_appointment(
    patient_name: str,
    patient_phone: str,
    service: str,
    starts_at: str,
    doctor_id: int,
    notes: str = None,
) -> str:
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    dt_start = datetime.fromisoformat(starts_at).astimezone(tz)
    dt_end = dt_start + timedelta(minutes=s.slot_duration_minutes)

    doctor = db.get_doctor_by_id(doctor_id)
    if not doctor:
        return "Error: doctor no encontrado. Por favor inténtalo de nuevo."

    service_slug = _normalize_slug(service)
    calendar_id = doctor["calendar_id"]
    event = cal.create_event(
        summary=f"{patient_name} - {service_slug}",
        starts_at=dt_start.isoformat(),
        ends_at=dt_end.isoformat(),
        calendar_id=calendar_id,
        description=notes,
    )

    patient = db.upsert_patient(patient_phone, patient_name)
    db.save_appointment(
        patient_id=patient["id"],
        google_event_id=event["id"],
        starts_at=dt_start.isoformat(),
        ends_at=dt_end.isoformat(),
        service=service_slug,
        doctor_id=doctor_id,
        calendar_id=calendar_id,
    )

    label = dt_start.strftime("%-d %b a las %H:%M")
    return (
        f"Cita confirmada ✅\n"
        f"• Paciente: {patient_name}\n"
        f"• Servicio: {service_slug}\n"
        f"• Doctor/a: {doctor['name']}\n"
        f"• Fecha: {label}"
    )


def tool_reschedule_appointment(patient_phone: str, new_starts_at: str) -> str:
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    appt = db.get_next_appointment_by_phone(patient_phone)
    if not appt:
        return "No encontré ninguna cita confirmada próxima para ese número."

    calendar_id = appt.get("calendar_id") or s.google_calendar_id
    dt_start = datetime.fromisoformat(new_starts_at).astimezone(tz)
    dt_end = dt_start + timedelta(minutes=s.slot_duration_minutes)

    cal.update_event(appt["google_event_id"], dt_start.isoformat(), dt_end.isoformat(), calendar_id)
    db.update_appointment(appt["id"], starts_at=dt_start.isoformat(), ends_at=dt_end.isoformat())

    label = dt_start.strftime("%-d %b a las %H:%M")
    return f"Cita reagendada ✅\nNueva fecha: {label}"


def tool_cancel_appointment(patient_phone: str, skip_followup: bool = False) -> str:
    s = get_settings()
    appt = db.get_next_appointment_by_phone(patient_phone)
    if not appt:
        return "No encontré ninguna cita confirmada próxima para ese número."

    calendar_id = appt.get("calendar_id") or s.google_calendar_id
    cal.cancel_event(appt["google_event_id"], calendar_id)
    db.update_appointment(
        appt["id"],
        status="cancelled",
        cancelled_at=datetime.utcnow().isoformat(),
        skip_post_cancellation_followup=skip_followup,
    )
    return "Cita cancelada ✅. Si quieres otra, dímelo y buscamos un hueco."


def tool_lookup_faq(query: str) -> str:
    faqs = db.search_faqs(query)
    if not faqs:
        return "No encontré información sobre eso en nuestra base de datos."
    parts = [f"**{f['question']}**\n{f['answer']}" for f in faqs]
    return "\n\n".join(parts)


def tool_close_conversation(conversation_id: int, db_conversation_id: str) -> str:
    try:
        chatwoot.update_conversation_status(conversation_id, "resolved")
    except Exception:
        logger.exception("Failed to resolve conversation in Chatwoot (continuing)")
    try:
        db.update_conversation_status(db_conversation_id, "closed")
    except Exception:
        logger.exception("Failed to close conversation in DB (continuing)")
    return "ok"


def tool_escalate_to_human(
    reason: str,
    summary: str,
    conversation_id: int,
    db_conversation_id: str,
) -> str:
    s = get_settings()

    try:
        db.save_escalation(db_conversation_id, reason)
        db.update_conversation_status(db_conversation_id, "escalated")
    except Exception:
        logger.exception("Failed to save escalation to DB (continuing)")

    try:
        chatwoot.add_private_note(
            conversation_id,
            f"🤖 Escalación automática\n**Motivo:** {reason}\n**Resumen:** {summary}",
        )
        chatwoot.add_label(conversation_id, ["escalado"])
        chatwoot.assign_conversation(conversation_id, s.chatwoot_bot_user_id)
        chatwoot.update_conversation_status(conversation_id, "open")
    except Exception:
        logger.exception("Failed to update Chatwoot for escalation (continuing)")

    alert_phone = s.escalation_alert_phone
    if alert_phone and s.meta_graph_token and s.meta_phone_number_id:
        cw_base = s.chatwoot_base_url.rstrip("/")
        alert_body = (
            f"🚨 Escalación PDV bot\n"
            f"Motivo: {reason}\n"
            f"Resumen: {summary}\n"
            f"Abrir conversación: {cw_base}/app/accounts/{s.chatwoot_account_id}/conversations/{conversation_id}"
        )
        try:
            wa.send_text(alert_phone, alert_body)
        except Exception:
            logger.exception("Failed to send escalation alert via WhatsApp")

    return (
        "Te paso con una persona del equipo, te contactarán en breve 😊 "
        "Si es urgente puedes llamar al 93 729 4880."
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "close_conversation": tool_close_conversation,
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
