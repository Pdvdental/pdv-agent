# PDV Agent

Agente conversacional de WhatsApp para PDV Policlínica Dental del Vallès.

**Stack:** Python 3.11 · FastAPI · Google Gemini 2.5 Flash · Supabase · Google Calendar API · Chatwoot · Railway

## Arquitectura

```
Paciente → WhatsApp → Meta → Chatwoot → PDV Agent (FastAPI) → Chatwoot → Meta → Paciente
                                ↑                                   ↓
                                └────── Recepcionista (app móvil) ──┘
```

## Estructura

```
app/
  agent/        — gemini_client.py, tools.py, prompt.py
  handlers/     — webhook.py, conversation.py, reminders.py
  integrations/ — chatwoot.py, calendar.py, db.py
  config.py
  main.py
  models.py
scripts/
  init_db.sql
  seed_faqs.py
  google_oauth_setup.py
tests/
```

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Rellena el .env
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -v
```

## Despliegue

Ver [DEPLOY.md](DEPLOY.md).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Healthcheck |
| POST | `/webhook/chatwoot` | Recibe eventos de Chatwoot (mensajes WhatsApp) |
| POST | `/internal/run-reminders` | Cron de recordatorios 24h (header `X-Internal-Token`) |