from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid


class Patient(BaseModel):
    id: Optional[uuid.UUID] = None
    phone_e164: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    chatwoot_contact_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Conversation(BaseModel):
    id: Optional[uuid.UUID] = None
    patient_id: uuid.UUID
    status: str = "active"  # active|escalated|closed
    chatwoot_conversation_id: Optional[int] = None
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Appointment(BaseModel):
    id: Optional[uuid.UUID] = None
    patient_id: uuid.UUID
    google_event_id: str
    starts_at: datetime
    ends_at: datetime
    service: Optional[str] = None
    status: str = "confirmed"  # confirmed|cancelled|completed
    reminder_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Message(BaseModel):
    id: Optional[uuid.UUID] = None
    conversation_id: uuid.UUID
    role: str  # user|model|tool
    content: str
    tool_calls: Optional[dict] = None
    tool_response: Optional[dict] = None
    chatwoot_message_id: Optional[int] = None
    created_at: Optional[datetime] = None


class FAQ(BaseModel):
    id: Optional[uuid.UUID] = None
    question: str
    answer: str
    category: Optional[str] = None
    active: bool = True


class Escalation(BaseModel):
    id: Optional[uuid.UUID] = None
    conversation_id: uuid.UUID
    reason: str
    resolved: bool = False
    created_at: Optional[datetime] = None