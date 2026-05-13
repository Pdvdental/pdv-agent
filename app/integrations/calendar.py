from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
from functools import lru_cache
import pytz

from app.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_service():
    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=s.google_refresh_token,
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)


def _tz() -> pytz.BaseTzInfo:
    return pytz.timezone(get_settings().timezone)


def _parse_time(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def check_availability(doctors: list[dict], date_from: str, date_to: str) -> list[dict]:
    """Returns up to 8 free slots across all given doctors between date_from and date_to."""
    tz = _tz()
    service = _build_service()

    dt_from = datetime.fromisoformat(date_from).astimezone(tz)
    dt_to = datetime.fromisoformat(date_to).astimezone(tz)

    freebusy = service.freebusy().query(body={
        "timeMin": dt_from.isoformat(),
        "timeMax": dt_to.isoformat(),
        "items": [{"id": d["calendar_id"]} for d in doctors],
    }).execute()

    all_slots = []

    for doctor in doctors:
        cal_id = doctor["calendar_id"]
        busy = [
            (datetime.fromisoformat(b["start"]).astimezone(tz),
             datetime.fromisoformat(b["end"]).astimezone(tz))
            for b in freebusy["calendars"].get(cal_id, {}).get("busy", [])
        ]

        working_days = doctor["working_days"]
        start_h, start_m = _parse_time(doctor["hours_start"])
        end_h, end_m = _parse_time(doctor["hours_end"])
        duration = doctor.get("slot_duration_minutes", 30)

        slots = []
        day_start = dt_from.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        current = max(day_start, dt_from.replace(second=0, microsecond=0))

        while current < dt_to and len(slots) < 5:
            if current.isoweekday() not in working_days:
                current += timedelta(days=1)
                current = current.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                continue

            slot_end = current + timedelta(minutes=duration)
            day_end = current.replace(hour=end_h, minute=end_m)

            if slot_end > day_end:
                current += timedelta(days=1)
                current = current.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                continue

            overlaps = any(b_start < slot_end and b_end > current for b_start, b_end in busy)
            if not overlaps and current > datetime.now(tz):
                slots.append({
                    "doctor_id": doctor["id"],
                    "doctor_name": doctor["name"],
                    "calendar_id": cal_id,
                    "starts_at": current.isoformat(),
                    "ends_at": slot_end.isoformat(),
                    "label": current.strftime("%-d %b, %H:%M"),
                })

            current += timedelta(minutes=duration)

        all_slots.extend(slots)

    all_slots.sort(key=lambda s: s["starts_at"])
    return all_slots[:8]


def create_event(
    summary: str,
    starts_at: str,
    ends_at: str,
    calendar_id: str,
    description: str = None,
) -> dict:
    s = get_settings()
    body = {
        "summary": summary,
        "start": {"dateTime": starts_at, "timeZone": s.timezone},
        "end": {"dateTime": ends_at, "timeZone": s.timezone},
    }
    if description:
        body["description"] = description
    service = _build_service()
    return service.events().insert(calendarId=calendar_id, body=body).execute()


def update_event(event_id: str, starts_at: str, ends_at: str, calendar_id: str) -> dict:
    s = get_settings()
    service = _build_service()
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    event["start"] = {"dateTime": starts_at, "timeZone": s.timezone}
    event["end"] = {"dateTime": ends_at, "timeZone": s.timezone}
    return service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()


def cancel_event(event_id: str, calendar_id: str) -> None:
    """Mark an event as cancelled (red color + ANULADO prefix) instead of deleting it."""
    service = _build_service()
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    summary = event.get("summary", "")
    if not summary.startswith("ANULADO"):
        event["summary"] = f"ANULADO - {summary}"
    event["colorId"] = "3"  # red — matches the "ANULADO" calendar color
    service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
