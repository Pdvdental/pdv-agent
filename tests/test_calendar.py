from unittest.mock import patch, MagicMock
from datetime import datetime
import pytz
import pytest

from app.integrations.calendar import check_availability


MADRID = pytz.timezone("Europe/Madrid")

MOCK_SETTINGS = MagicMock(
    timezone="Europe/Madrid",
    slot_duration_minutes=30,
    working_hours_start="09:00",
    working_hours_end="20:00",
    working_days_list=[1, 2, 3, 4],
    google_calendar_id="primary",
    google_client_id="x",
    google_client_secret="x",
    google_refresh_token="x",
)


def _make_freebusy(busy_periods: list[tuple[str, str]]) -> dict:
    return {
        "calendars": {
            "primary": {
                "busy": [{"start": s, "end": e} for s, e in busy_periods]
            }
        }
    }


@patch("app.integrations.calendar.get_settings", return_value=MOCK_SETTINGS)
@patch("app.integrations.calendar._build_service")
def test_check_availability_returns_slots(mock_service, mock_settings):
    mock_fb = MagicMock()
    mock_fb.query.return_value.execute.return_value = _make_freebusy([])
    mock_service.return_value.freebusy.return_value = mock_fb

    slots = check_availability(
        "2026-05-05T00:00:00+02:00",
        "2026-05-05T23:59:59+02:00",
    )
    assert len(slots) > 0
    assert all("starts_at" in s and "ends_at" in s for s in slots)


@patch("app.integrations.calendar.get_settings", return_value=MOCK_SETTINGS)
@patch("app.integrations.calendar._build_service")
def test_check_availability_excludes_busy(mock_service, mock_settings):
    busy = [
        ("2026-05-05T09:00:00+02:00", "2026-05-05T12:00:00+02:00"),
    ]
    mock_fb = MagicMock()
    mock_fb.query.return_value.execute.return_value = _make_freebusy(busy)
    mock_service.return_value.freebusy.return_value = mock_fb

    slots = check_availability(
        "2026-05-05T00:00:00+02:00",
        "2026-05-05T23:59:59+02:00",
    )
    for slot in slots:
        start = datetime.fromisoformat(slot["starts_at"]).astimezone(MADRID)
        assert not (start.hour >= 9 and start.hour < 12), f"Slot {slot} overlaps busy period"


@patch("app.integrations.calendar.get_settings", return_value=MOCK_SETTINGS)
@patch("app.integrations.calendar._build_service")
def test_check_availability_max_8_slots(mock_service, mock_settings):
    mock_fb = MagicMock()
    mock_fb.query.return_value.execute.return_value = _make_freebusy([])
    mock_service.return_value.freebusy.return_value = mock_fb

    slots = check_availability(
        "2026-05-04T00:00:00+02:00",
        "2026-05-10T23:59:59+02:00",
    )
    assert len(slots) <= 8


@patch("app.integrations.calendar.get_settings", return_value=MOCK_SETTINGS)
@patch("app.integrations.calendar._build_service")
def test_check_availability_respects_working_days(mock_service, mock_settings):
    mock_fb = MagicMock()
    mock_fb.query.return_value.execute.return_value = _make_freebusy([])
    mock_service.return_value.freebusy.return_value = mock_fb

    # 2026-05-08 is Friday (isoweekday=5), 2026-05-09 is Saturday (6)
    slots = check_availability(
        "2026-05-08T00:00:00+02:00",
        "2026-05-09T23:59:59+02:00",
    )
    assert slots == [], f"Expected no slots on Fri/Sat, got {slots}"