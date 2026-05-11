# PDV Agent — Contexto para Claude

Agente conversacional WhatsApp para Policlínica Dental del Vallès (PDV), Barberà del Vallès, Barcelona.

## Estado actual (2026-05-11) — SISTEMA EN PRODUCCIÓN ✅

El bot funciona en el número real de la clínica (+34678837755). Un paciente puede escribir por WhatsApp, el bot responde, consulta disponibilidad en Google Calendar y reserva citas.

## Stack
- Python 3.11 + FastAPI (este repo)
- Google Gemini 2.5 Flash — LLM con function calling
- Supabase (Postgres) — pacientes, conversaciones, citas, FAQs
- Google Calendar API — disponibilidad y reservas
- Chatwoot v3.10.1 en Railway — intermediario WhatsApp ↔ bot
- WhatsApp Business Cloud API (Meta) — número real +34678837755
- Railway — despliegue en https://pdv-agent-production.up.railway.app

## Infraestructura

### Railway (proyecto: rare-forgiveness)
- `chatwoot` → https://chatwoot-production-3e3a.up.railway.app
- `pdv-agent` → https://pdv-agent-production.up.railway.app
- Postgres + Redis también en Railway

### Chatwoot
- Account ID: 2, Admin: Vanessa (policlinicadentaldelvalles@gmail.com)
- Agent Bot "PDV Agent" ID=1, token=tpGybpZU6G8oL81DVsS57V3b
- Inbox 1: número prueba +15556346898 (PHONE_ID: 1075184422345689, WABA: 959652206921524)
- Inbox 2: número real +34678837755 (PHONE_ID: 1175481288972384, WABA: 2194558867949255) ✅ activo
- **Crítico**: Chatwoot enruta webhooks por `phone_number_id` del payload, NO por URL path. Ambos inboxes usan la misma URL: `/webhooks/whatsapp/+15556346898`
- **Crítico**: send_message debe usar token del agent bot (CHATWOOT_HMAC_TOKEN), no el admin token
- **Crítico**: bot webhook solo se dispara para conversaciones en status "pending"

### Meta
- App: PDV Dental Agent (ID: 942429122010271)
- Token: EAANZAImELHJ8BRaijv6IcbtpOUZAaPEeCs3lNCjUOpI3t8wrPyNQMkrPJv23tZA1ueM4fTIeRXZC28ZBdh4W7UveNoWIrh9NOM7ZALuN79USHZCipvB0bERwZAeb0m4v2AoRUIDSK0NkICeH9D0ZBRY3J8YqV4QZBh64oDBFxcbKKweEeL46r0PuMgawKXUToypOZCkMgZDZD
- Token caduca ~2026-07-05 → renovar en Meta Business Manager → Usuarios del sistema → pdv-agent
- Webhook URL: `https://chatwoot-production-3e3a.up.railway.app/webhooks/whatsapp/+15556346898`
- Verify token: `27f818781fd6e81065e19bb371854b1b`
- Plantilla `cita_recordatorio_pdv`: estado PENDING en Meta (es_MX, 4 params: nombre, fecha, hora, servicio)

### Google Calendar OAuth
- Client ID: 628094446493-3cv505bb3jr9m3il9n1d67195oq8gidh.apps.googleusercontent.com
- Refresh token renovado 2026-05-07 (el anterior caducó por inactividad)
- Si da `invalid_grant`: ejecutar `scripts/get_refresh_token.py` y actualizar GOOGLE_REFRESH_TOKEN en Railway

### Supabase
- URL: https://gbyxlraihcpctqxnkwjy.supabase.co
- Tablas: `patients`, `conversations`, `appointments`, `faqs`
- 12 FAQs cargadas

---

## PRÓXIMA TAREA: Arquitectura multi-doctor

### Por qué
El sistema actual usa un único Google Calendar con horario global. La clínica tiene 4 doctores activos con horarios variables y tratamientos específicos por doctor.

### Doctores confirmados

| Doctor | Tratamientos | Horario | Calendar Google |
|--------|-------------|---------|-----------------|
| AINA | Ortodoncia | Mié ~cada 14 días, 14-20h | Calendar "Ortodoncia" → **pendiente renombrar + ID** |
| LAURYS | Odont. General, limpieza, revisiones, caries | Jue 11-19:30 / Mar variable mañanas | Calendar "Laurys" → **pendiente ID** |
| MILA (Maria Milagros) | Odont. General | Mar 11-20:30 / Mié 10-14 | Calendar "Odonto General" → **pendiente renombrar + ID** |
| VANESSA | — | Siempre escala a humano | No necesita calendar |

**Estado**: Vanessa necesita confirmar el mapeo de nombres de calendario → doctor y compartir los Calendar IDs.

Calendarios actuales en Google Calendar de Vanessa: "Policlínica Dental del Vallès", "ANULADO", "Cirujano", "Endodoncia", "Laurys", "Odonto General" (x2), "Odontología General", "Ortodoncia"

### Plan de implementación

#### 1. Nuevas tablas en Supabase
```sql
CREATE TABLE doctors (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  calendar_id TEXT NOT NULL,
  hours_start TEXT NOT NULL,
  hours_end TEXT NOT NULL,
  working_days INTEGER[] NOT NULL,  -- ISO: 1=Lun, 7=Dom
  slot_duration_minutes INTEGER DEFAULT 30,
  active BOOLEAN DEFAULT TRUE
);

CREATE TABLE doctor_services (
  doctor_id INTEGER REFERENCES doctors(id),
  service_slug TEXT NOT NULL,
  PRIMARY KEY (doctor_id, service_slug)
);
```

#### 2. Cambios en el código
- `app/integrations/calendar.py`: `check_availability(doctors: list[dict])` — acepta lista de doctores con su calendar_id y horario; devuelve slots con `doctor_id`
- `app/integrations/db.py`: añadir `get_doctors_for_service(service_slug)` y `get_all_active_doctors()`
- `app/agent/tools.py`: modificar tool de disponibilidad para (1) detectar tratamiento → (2) buscar doctores elegibles → (3) si solo Vanessa → escalar → (4) consultar calendarios
- `app/config.py`: las variables globales `working_hours_start/end`, `working_days`, `slot_duration_minutes` pasan a nivel doctor

#### 3. Flujo del bot con multi-doctor
1. Paciente pide tratamiento X
2. Bot busca en `doctor_services` qué doctores hacen X
3. Si solo está Vanessa → respuesta: "Para este tratamiento contacta directamente con la clínica al 93 729 4880"
4. Si hay ≥1 doctor automatable → consultar sus calendarios → ofrecer slots (indicar doctor si hay varios)
5. Al confirmar → crear evento en el calendario del doctor elegido

---

## Diagnóstico rápido del sistema

```bash
# Health check pdv-agent
curl -s https://pdv-agent-production.up.railway.app/health

# Conversaciones pendientes
curl -s "https://chatwoot-production-3e3a.up.railway.app/api/v1/accounts/2/conversations?status=pending" \
  -H "api_access_token: Ujbzu7dGCeytF5KwYK8oG9FM" | grep -o '"all_count":[0-9]*'

# Estado WABA producción
curl -s "https://graph.facebook.com/v19.0/2194558867949255/subscribed_apps?access_token=TOKEN"
```

Para diagnóstico completo usar el skill `/pdv check` si está disponible (en `~/.claude/skills/pdv-check.md`).

## Fix rápido — Chatwoot deja de procesar webhooks

```bash
# 1. PATCH inbox 2 con config completa
curl -X PATCH "https://chatwoot-production-3e3a.up.railway.app/api/v1/accounts/2/inboxes/2" \
  -H "api_access_token: Ujbzu7dGCeytF5KwYK8oG9FM" \
  -H "Content-Type: application/json" \
  -d '{"channel":{"provider_config":{"api_key":"EAANZAImELHJ8BRaijv6IcbtpOUZAaPEeCs3lNCjUOpI3t8wrPyNQMkrPJv23tZA1ueM4fTIeRXZC28ZBdh4W7UveNoWIrh9NOM7ZALuN79USHZCipvB0bERwZAeb0m4v2AoRUIDSK0NkICeH9D0ZBRY3J8YqV4QZBh64oDBFxcbKKweEeL46r0PuMgawKXUToypOZCkMgZDZD","app_secret":"e8edecd980ed6152946a49500a93849d","phone_number_id":"1175481288972384","business_account_id":"2194558867949255","webhook_verify_token":"pdv678verify2026"}}}'
# 2. Railway → chatwoot → Restart
# 3. Meta for Developers → Verify and Save (URL: /webhooks/whatsapp/+15556346898, token: 27f818781fd6e81065e19bb371854b1b)
```

## Fix rápido — Mensaje sin respuesta (bot estaba redeployando)

```bash
curl -X POST "https://pdv-agent-production.up.railway.app/webhook/chatwoot" \
  -H "Content-Type: application/json" \
  -d '{"event":"message_created","message_type":"incoming","id":MSG_ID,"content":"MENSAJE","account":{"id":2},"conversation":{"id":CONV_ID,"status":"pending","inbox_id":2,"labels":[],"meta":{"sender":{"id":CONTACT_ID,"name":"Nombre","phone_number":"+34XXXXXXXXX"},"assignee":null}},"sender":{"id":CONTACT_ID,"name":"Nombre","phone_number":"+34XXXXXXXXX"}}'
```