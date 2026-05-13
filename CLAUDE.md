# PDV Agent — Contexto para Claude

Agente conversacional WhatsApp para Policlínica Dental del Vallès (PDV), Barberà del Vallès, Barcelona.

## Estado actual (2026-05-13) — SISTEMA EN PRODUCCIÓN ✅

El bot funciona en el número real de la clínica (+34678837755). Reserva citas, reagenda, cancela, escala a humano y reconoce pacientes recurrentes. El flujo pasa directamente Meta→bot (bypass Chatwoot worker).

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
- Plantillas: ver sección "Plantillas Meta WhatsApp" en Supabase más abajo

### Google Calendar OAuth
- Client ID: 628094446493-3cv505bb3jr9m3il9n1d67195oq8gidh.apps.googleusercontent.com
- Refresh token renovado 2026-05-07 (el anterior caducó por inactividad)
- Si da `invalid_grant`: ejecutar `scripts/get_refresh_token.py` y actualizar GOOGLE_REFRESH_TOKEN en Railway

### Supabase
- URL: https://gbyxlraihcpctqxnkwjy.supabase.co
- Tablas: `patients`, `conversations`, `messages`, `appointments`, `faqs`, `doctors`, `doctor_services`, `escalations`
- 12 FAQs cargadas
- `appointments` tiene columnas extra: `doctor_id`, `calendar_id`, `cancelled_at`, `post_cancellation_followup_sent_at`, `skip_post_cancellation_followup`

### Plantillas Meta WhatsApp
- `cita_recordatorio_pdv`: estado PENDING (4 params: nombre, fecha, hora, servicio) — se usa con `REMINDERS_ENABLED=true`
- `cita_seguimiento_pdv`: **pendiente de crear** en Meta Business Manager (2 params: nombre, servicio) — se usa con `POST_CANCELLATION_FOLLOWUPS_ENABLED=true`

---

## Arquitectura multi-doctor ✅ (implementado 2026-05-12)

| Doctor | Tratamientos | Horario | Calendar Google |
|--------|-------------|---------|-----------------|
| AINA OLIVART | Ortodoncia | Mié ~cada 14 días, 14-20h | Calendar "Dra. AINA OLIVART" (colorId=6) |
| LAURYS ARAB | Odont. General, limpieza, revisiones, caries | Jue 10-19:30 / Mar mañanas | Calendar "Dra. LAURYS ARAB" (colorId=18) |
| MILA (María Milagros Cardozo) | Odont. General | Mar 11-20:30 / Mié 10-14 | Calendar "Dra. MARÍA MILAGROS CARDOZO" (colorId=20) |
| VANESSA | — | No gestiona agenda por bot | No necesita calendar |

**Flujo:** paciente pide servicio X → bot busca en `doctor_services` qué doctores lo hacen → consulta freebusy de sus calendarios → ofrece slots con nombre de doctora → reserva en el calendar correcto.

**Vanessa:** si el paciente pide cita con Vanessa, el bot ofrece disponibilidad con otras doctoras primero. Solo escala si el paciente insiste explícitamente.

**Calendario ANULADO:** `colorId=3` (#f83a22, rojo). Cuando se cancela una cita, el evento de Google Calendar se marca con ese color y prefijo "ANULADO - " en lugar de borrarse.

## Features de automatización

| Feature | Estado | Variable Railway |
|---------|--------|-----------------|
| Recordatorio 24h antes de cita | Código listo ✅, inactivo | `REMINDERS_ENABLED=false` |
| Seguimiento post-cancelación 20 días | Código listo ✅, inactivo | `POST_CANCELLATION_FOLLOWUPS_ENABLED=false` |

**Para activar recordatorios:** requiere que Meta apruebe `cita_recordatorio_pdv` (estado PENDING).
**Para activar seguimiento:** requiere crear y aprobar plantilla `cita_seguimiento_pdv` en Meta (2 params: nombre, servicio). Cuerpo sugerido: *"Hola {{1}} 😊 Vimos que cancelaste tu cita de {{2}}. ¿Te gustaría que te buscara un nuevo hueco? Escríbeme y lo gestionamos enseguida, o si prefieres puedes llamar al 93 729 4880 🦷"*

## Otras features activas

- **Reconocimiento de pacientes**: el bot saluda por nombre si ya tiene historial (`patient_name` inyectado en el prompt)
- **Teléfono en contexto**: `phone_e164` inyectado siempre — el bot nunca pide el teléfono si ya lo tiene
- **close_conversation**: cuando el paciente se despide, el bot cierra la conversación en Chatwoot (status "resolved") y en DB ("closed")
- **Bypass directo Meta→bot**: `DIRECT_HANDLER_ENABLED=true` — evita el worker Sidekiq de Chatwoot que muere silenciosamente. Chatwoot solo sirve como panel de gestión.

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