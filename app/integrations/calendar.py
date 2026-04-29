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


def check_availability(date_from: str, date_to: str, duration_minutes: int = None) -> list[dict]:
    """Returns up to 8 free slots between date_from and date_to."""
    s = get_settings()
    tz = _tz()
    duration = duration_minutes or s.slot_duration_minutes
    start_h, start_m = _parse_time(s.working_hours_start)
    end_h, end_m = _parse_time(s.working_hours_end)

    service = _build_service()
    dt_from = datetime.fromisoformat(date_from).astimezone(tz)
    dt_to = datetime.fromisoformat(date_to).astimezone(tz)

    freebusy = service.freebusy().query(body={
        "timeMin": dt_from.isoformat(),
        "timeMax": dt_to.isoformat(),
        "items": [{"id": s.google_calendar_id}],
    }).execute()

    busy = [
        (datetime.fromisoformat(b["start"]).astimezone(tz),
         datetime.fromisoformat(b["end"]).astimezone(tz))
        for b in freebusy["calendars"][s.google_calendar_id].get("busy", [])
    ]

    slots = []
    current = dt_from.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    while current < dt_to and len(slots) < 8:
        # Skip non-working days (ISO weekday: 1=Mon, 7=Sun)
        if current.isoweekday() not in s.working_days_list:
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
                "starts_at": current.isoformat(),
                "ends_at": slot_end.isoformat(),
                "label": current.strftime("%-d %b, %H:%M"),
            })

        current += timedelta(minutes=duration)

    return slots


def create_event(
    summary: str,
    starts_at: str,
    ends_at: str,
    description: str = None,
) -> dict:
    s = get_settings()
    tz = _tz()
    body = {
        "summary": summary,
        "start": {"dateTime": starts_at, "timeZone": s.timezone},
        "end": {"dateTime": ends_at, "timeZone": s.timezone},
    }
    if description:
        body["description"] = description
    service = _build_service()
    event = service.events().insert(calendarId=s.google_calendar_id, body=body).execute()
    return event


def update_event(event_id: str, starts_at: str, ends_at: str) -> dict:
    s = get_settings()
    service = _build_service()
    event = service.events().get(calendarId=s.google_calendar_id, eventId=event_id).execute()
    event["start"] = {"dateTime": starts_at, "timeZone": s.timezone}
    event["end"] = {"dateTime": ends_at, "timeZone": s.timezone}
    updated = service.events().update(calendarId=s.google_calendar_id, eventId=event_id, body=event).execute()
    return updated


def delete_event(event_id: str) -> None:
    s = get_settings()
    service = _build_service()
    service.events().delete(calendarId=s.google_calendar_id, eventId=event_id).execute()