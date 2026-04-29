-- PDV Agent — Supabase schema
-- Run from: Supabase Dashboard → SQL Editor

create table if not exists patients (
  id uuid primary key default gen_random_uuid(),
  phone_e164 text unique not null,
  full_name text,
  email text,
  notes text,
  chatwoot_contact_id integer unique,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  status text default 'active',              -- active|escalated|closed
  chatwoot_conversation_id integer unique,
  last_message_at timestamptz default now(),
  created_at timestamptz default now()
);
create index if not exists idx_conv_patient on conversations(patient_id);
create index if not exists idx_conv_chatwoot on conversations(chatwoot_conversation_id);

create table if not exists appointments (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  google_event_id text unique not null,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  service text,
  status text default 'confirmed',           -- confirmed|cancelled|completed
  reminder_sent_at timestamptz,
  created_at timestamptz default now()
);
create index if not exists idx_appt_starts on appointments(starts_at);
create index if not exists idx_appt_reminder on appointments(starts_at, reminder_sent_at);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete cascade,
  role text not null,                        -- user|model|tool
  content text not null,
  tool_calls jsonb,
  tool_response jsonb,
  chatwoot_message_id integer,
  created_at timestamptz default now()
);
create index if not exists idx_msg_conv on messages(conversation_id, created_at);

create table if not exists faqs (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  answer text not null,
  category text,
  active boolean default true
);

create table if not exists escalations (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id),
  reason text not null,
  resolved boolean default false,
  created_at timestamptz default now()
);

-- Index for reminder lookup
create index if not exists idx_patient_chatwoot on patients(chatwoot_contact_id);