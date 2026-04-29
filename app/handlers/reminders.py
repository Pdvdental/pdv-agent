import logging
from datetime import datetime
import pytz

from app.config import get_settings
from app.integrations import db
from app.integrations import chatwoot

logger = logging.getLogger(__name__)


def run_reminders() -> dict:
    """
    Finds appointments in the 23-25h window without a reminder sent,
    sends a WhatsApp template via Chatwoot, and marks them as done.
    """
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    appointments = db.get_appointments_needing_reminder()
    sent = 0
    errors = 0

    for appt in appointments:
        patient = appt.get("patients", {})
        contact_id = patient.get("chatwoot_contact_id")
        if not contact_id:
            logger.warning(f"Appointment {appt['id']} has no chatwoot_contact_id, skipping reminder.")
            errors += 1
            continue

        try:
            starts_at = datetime.fromisoformat(appt["starts_at"]).astimezone(tz)
            name = patient.get("full_name") or "Paciente"
            date_str = starts_at.strftime("%-d de %B")
            time_str = starts_at.strftime("%H:%M")
            service = appt.get("service") or "tu cita"

            chatwoot.send_template(
                contact_id=contact_id,
                template_name="recordatorio_cita_24h",
                parameters=[name, date_str, time_str, service],
            )
            db.update_appointment(appt["id"], reminder_sent_at=datetime.utcnow().isoformat())
            sent += 1
            logger.info(f"Reminder sent for appointment {appt['id']} to {name}")
        except Exception as e:
            logger.error(f"Failed to send reminder for appointment {appt['id']}: {e}")
            errors += 1

    return {"sent": sent, "errors": errors, "total": len(appointments)}