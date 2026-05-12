from supabase import create_client, Client
from functools import lru_cache
from app.config import get_settings


@lru_cache
def get_db() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def upsert_patient(phone_e164: str, full_name: str = None, chatwoot_contact_id: int = None) -> dict:
    db = get_db()
    data = {"phone_e164": phone_e164}
    if full_name:
        data["full_name"] = full_name
    if chatwoot_contact_id is not None:
        data["chatwoot_contact_id"] = chatwoot_contact_id
    res = db.table("patients").upsert(data, on_conflict="phone_e164").execute()
    return res.data[0]


def get_patient_by_phone(phone_e164: str) -> dict | None:
    db = get_db()
    res = db.table("patients").select("*").eq("phone_e164", phone_e164).limit(1).execute()
    return res.data[0] if res.data else None


def get_or_create_conversation(patient_id: str, chatwoot_conversation_id: int) -> dict:
    db = get_db()
    res = (
        db.table("conversations")
        .select("*")
        .eq("chatwoot_conversation_id", chatwoot_conversation_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]
    new = (
        db.table("conversations")
        .insert({
            "patient_id": patient_id,
            "chatwoot_conversation_id": chatwoot_conversation_id,
            "status": "active",
        })
        .execute()
    )
    return new.data[0]


def get_conversation_messages(conversation_id: str, limit: int = 30) -> list[dict]:
    db = get_db()
    res = (
        db.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_calls: dict = None,
    tool_response: dict = None,
    chatwoot_message_id: int = None,
    source_id: str = None,
) -> dict:
    db = get_db()
    data = {"conversation_id": conversation_id, "role": role, "content": content}
    if tool_calls:
        data["tool_calls"] = tool_calls
    if tool_response:
        data["tool_response"] = tool_response
    if chatwoot_message_id is not None:
        data["chatwoot_message_id"] = chatwoot_message_id
    if source_id is not None:
        data["source_id"] = source_id
    res = db.table("messages").insert(data).execute()
    return res.data[0]


def message_exists_by_source_id(source_id: str) -> bool:
    if not source_id:
        return False
    db = get_db()
    res = db.table("messages").select("id").eq("source_id", source_id).limit(1).execute()
    return bool(res.data)


def update_conversation_status(conversation_id: str, status: str) -> None:
    db = get_db()
    db.table("conversations").update({"status": status}).eq("id", conversation_id).execute()


def search_faqs(query: str, limit: int = 3) -> list[dict]:
    db = get_db()
    words = query.lower().split()
    res = db.table("faqs").select("*").eq("active", True).execute()
    faqs = res.data

    def score(faq: dict) -> int:
        text = (faq["question"] + " " + faq["answer"]).lower()
        return sum(1 for w in words if w in text)

    ranked = sorted(faqs, key=score, reverse=True)
    return ranked[:limit]


def save_appointment(
    patient_id: str,
    google_event_id: str,
    starts_at: str,
    ends_at: str,
    service: str = None,
) -> dict:
    db = get_db()
    res = (
        db.table("appointments")
        .insert({
            "patient_id": patient_id,
            "google_event_id": google_event_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "service": service,
            "status": "confirmed",
        })
        .execute()
    )
    return res.data[0]


def get_next_appointment_by_phone(phone_e164: str) -> dict | None:
    db = get_db()
    patient = get_patient_by_phone(phone_e164)
    if not patient:
        return None
    res = (
        db.table("appointments")
        .select("*")
        .eq("patient_id", patient["id"])
        .eq("status", "confirmed")
        .gte("starts_at", "now()")
        .order("starts_at")
        .limit(1)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def update_appointment(appointment_id: str, **kwargs) -> dict:
    db = get_db()
    res = db.table("appointments").update(kwargs).eq("id", appointment_id).execute()
    return res.data[0]


def get_appointments_needing_reminder() -> list[dict]:
    db = get_db()
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    window_start = (now + timedelta(hours=23)).isoformat()
    window_end = (now + timedelta(hours=25)).isoformat()
    res = (
        db.table("appointments")
        .select("*, patients(phone_e164, full_name, chatwoot_contact_id)")
        .eq("status", "confirmed")
        .is_("reminder_sent_at", "null")
        .gte("starts_at", window_start)
        .lte("starts_at", window_end)
        .execute()
    )
    return res.data


def save_escalation(conversation_id: str, reason: str) -> dict:
    db = get_db()
    res = db.table("escalations").insert({"conversation_id": conversation_id, "reason": reason}).execute()
    return res.data[0]