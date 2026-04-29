# Guía de despliegue — PDV Agent
**Para el equipo de la clínica. No se necesitan conocimientos técnicos.**
Tiempo estimado: 4-5 horas la primera vez.

---

## Antes de empezar — cuentas que necesitas crear

Crea estas cuentas antes de empezar. Todas son gratuitas salvo donde se indica.

| Servicio | Para qué | URL |
|---|---|---|
| Meta for Developers | WhatsApp Business API | developers.facebook.com |
| Google AI Studio | API de Gemini (el cerebro del bot) | aistudio.google.com |
| Google Cloud | API de Google Calendar | console.cloud.google.com |
| Supabase | Base de datos del bot | supabase.com |
| Railway | Servidor donde corre todo | railway.app (~10-15 €/mes) |
| GitHub | Guardar el código | github.com |
| Resend o Brevo | Emails de Chatwoot | resend.com (gratuito hasta 3000/mes) |

---

## Paso 1 — GitHub: subir el código

1. Crea un repositorio en GitHub llamado `pdv-agent` (privado).
2. Sube la carpeta `pdv-agent/` de este proyecto.

---

## Paso 2 — Railway: crear el proyecto y las bases de datos

1. Entra en railway.app → **New Project**.
2. **New Service → Database → PostgreSQL**. Nómbralo `pdv-postgres`. Guarda el `DATABASE_URL`.
3. **New Service → Database → Redis**. Nómbralo `pdv-redis`. Guarda el `REDIS_URL`.

---

## Paso 3 — Chatwoot: desplegar y configurar

### 3.1 Crear el servicio Chatwoot

1. En Railway → **New Service → Empty Service**. Nombre: `chatwoot`.
2. Source: **Deploy from Docker Image** → imagen: `chatwoot/chatwoot:latest`
3. Start Command:
   ```
   bundle exec rails db:chatwoot_prepare && bundle exec rails s -p $PORT -b 0.0.0.0
   ```
4. Genera un dominio público: **Settings → Networking → Generate Domain**.
   Anota la URL, ej: `https://chatwoot-pdv.up.railway.app`

5. Añade estas variables de entorno en Railway para el servicio `chatwoot`:

   | Variable | Valor |
   |---|---|
   | `SECRET_KEY_BASE` | Genera 64 caracteres aleatorios (usa [randomkeygen.com](https://randomkeygen.com)) |
   | `FRONTEND_URL` | `https://chatwoot-pdv.up.railway.app` |
   | `DEFAULT_LOCALE` | `es` |
   | `RAILS_ENV` | `production` |
   | `NODE_ENV` | `production` |
   | `INSTALLATION_ENV` | `docker` |
   | `POSTGRES_HOST` | Host del `pdv-postgres` (en Railway → pdv-postgres → Connect) |
   | `POSTGRES_DATABASE` | `chatwoot_production` |
   | `POSTGRES_USERNAME` | Usuario del postgres (en Railway → pdv-postgres → Connect) |
   | `POSTGRES_PASSWORD` | Contraseña del postgres |
   | `REDIS_URL` | URL del `pdv-redis` |
   | `SMTP_ADDRESS` | Servidor SMTP (Resend: `smtp.resend.com`) |
   | `SMTP_PORT` | `587` |
   | `SMTP_USERNAME` | Usuario SMTP (Resend: `resend`) |
   | `SMTP_PASSWORD` | API Key de Resend |
   | `SMTP_DOMAIN` | `pdvdental.es` |
   | `MAILER_SENDER_EMAIL` | `Chatwoot PDV <noreply@pdvdental.es>` |
   | `ACTIVE_STORAGE_SERVICE` | `local` |

6. Deploy → espera a que el servicio aparezca como **Active**.

### 3.2 Crear servicio Chatwoot Worker

1. **New Service → Empty Service**. Nombre: `chatwoot-worker`.
2. Misma imagen: `chatwoot/chatwoot:latest`
3. Start Command:
   ```
   bundle exec sidekiq -C config/sidekiq.yml
   ```
4. Añade **exactamente las mismas variables** que el servicio `chatwoot`. Sin dominio público.

### 3.3 Crear cuenta admin en Chatwoot

1. Abre `https://chatwoot-pdv.up.railway.app` en el navegador.
2. Te pedirá crear la primera cuenta de administrador.
3. Usa el email de la clínica y una contraseña segura.

---

## Paso 4 — WhatsApp Business API (Meta)

### 4.1 Verificar el número de teléfono

1. Ve a [developers.facebook.com](https://developers.facebook.com) → tu app → **WhatsApp → Getting Started**.
2. Verifica el número `677 523 665`. Meta enviará un SMS con código.
3. Anota el **Phone Number ID** y el **WhatsApp Business Account ID**.

### 4.2 Crear System User con token permanente

1. Ve a [business.facebook.com](https://business.facebook.com) → **Configuración del negocio → Sistema de usuarios**.
2. Crea un System User con rol "Administrador".
3. Asígnale permisos al número de teléfono.
4. Genera un token **sin caducidad**. Guárdalo como `WHATSAPP_ACCESS_TOKEN`.

### 4.3 Registrar la plantilla de recordatorio

Ve a **Meta Business Manager → WhatsApp → Plantillas de mensajes** y crea:

- **Nombre:** `recordatorio_cita_24h`
- **Idioma:** Español (es)
- **Categoría:** Utility
- **Cuerpo del mensaje:**
  ```
  Hola {{1}} 😊 Te recordamos tu cita en PDV Dental mañana {{2}} a las {{3}} para {{4}}.
  Si necesitas cambiarla, responde a este mensaje.
  PDV Policlínica Dental del Vallès | 93 729 4880
  ```

La aprobación tarda 24-48 horas.

### 4.4 Conectar WhatsApp a Chatwoot

1. En Chatwoot → **Settings → Inboxes → Add Inbox → WhatsApp → API Provider: Whatsapp Cloud**.
2. Rellena:
   - Phone Number: `+34677523665`
   - Phone Number ID: el que anotaste
   - Business Account ID: el que anotaste
   - Access Token: `WHATSAPP_ACCESS_TOKEN`
   - API Key (verify token): elige cualquier texto aleatorio, ej: `pdv-verify-2026`
3. Chatwoot te dará la URL del webhook: `https://chatwoot-pdv.up.railway.app/webhooks/whatsapp/+34677523665`
4. Ve a Meta → **WhatsApp → Configuration → Webhook** → pega esa URL + el verify token.
5. Suscríbete al evento `messages`.
6. Prueba: envía "hola" desde un móvil al `677`. Debe aparecer en Chatwoot.

---

## Paso 5 — Google Calendar API

1. Ve a [console.cloud.google.com](https://console.cloud.google.com) → **Nuevo Proyecto** (nombre: `PDV Agent`).
2. Habilitar API: **APIs y Servicios → Habilitar APIs → Google Calendar API**.
3. **Credenciales → Crear credenciales → ID de cliente OAuth 2.0** → Tipo: **Aplicación de escritorio**.
4. Descarga el JSON de credenciales.
5. Abre un terminal en la carpeta del proyecto y ejecuta:
   ```bash
   python scripts/google_oauth_setup.py
   ```
6. Se abre el navegador → inicia sesión con el Gmail de la clínica → autoriza.
7. El script te mostrará el `GOOGLE_REFRESH_TOKEN`. Guárdalo.

---

## Paso 6 — Supabase: crear la base de datos

1. Ve a [supabase.com](https://supabase.com) → **New Project**. Región: `eu-west-1` (Irlanda, la más cercana).
2. Anota la **Project URL** y la **service_role key** (en Settings → API).
3. Ve a **SQL Editor** → pega el contenido completo del archivo `scripts/init_db.sql` → ejecuta.
4. Verifica que las tablas aparecen en **Table Editor**: patients, conversations, appointments, messages, faqs, escalations.

---

## Paso 7 — Configurar y desplegar el bot en Railway

### 7.1 Crear el bot-user en Chatwoot

1. Chatwoot → **Settings → Agents → Invite Agent**.
2. Email: `bot@pdvdental.es` (puedes inventar este email, solo necesitas confirmar la invitación).
3. Una vez creado, inicia sesión con ese usuario → **Profile → Access Token** → copia el token.
4. Para obtener el ID del bot: con el token copiado, abre una terminal:
   ```bash
   curl https://chatwoot-pdv.up.railway.app/auth/sign_in \
     -H "api_access_token: <token_del_bot>"
   ```
   El campo `id` en la respuesta es el `CHATWOOT_BOT_USER_ID`.

### 7.2 Crear el Agent Bot en Chatwoot

1. Chatwoot → **Settings → Integrations → Agent Bots → New Agent Bot**.
2. Name: `PDV Agent`
3. Outgoing URL: `https://pdv-agent.up.railway.app/webhook/chatwoot` *(se completa en paso 7.4)*
4. Copia el **HMAC Token** que genera → es `CHATWOOT_HMAC_TOKEN`.
5. **Settings → Inboxes → WhatsApp inbox → tab "Bot Configuration" → selecciona `PDV Agent`**.

### 7.3 Desplegar el bot

1. Railway → **New Service → GitHub Repo** → selecciona `pdv-agent`.
2. Railway detecta el `Procfile` automáticamente.
3. **Settings → Networking → Generate Domain** → anota la URL, ej: `https://pdv-agent.up.railway.app`.

### 7.4 Variables de entorno del bot

Añade estas variables en Railway → servicio `pdv-agent` → **Variables**:

| Variable | Valor |
|---|---|
| `GEMINI_API_KEY` | Obtenido en aistudio.google.com/apikey |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `CHATWOOT_BASE_URL` | `https://chatwoot-pdv.up.railway.app` |
| `CHATWOOT_ACCOUNT_ID` | `1` |
| `CHATWOOT_INBOX_ID` | ID del inbox en Chatwoot (Settings → Inboxes) |
| `CHATWOOT_API_ACCESS_TOKEN` | Token del bot-user |
| `CHATWOOT_HMAC_TOKEN` | Token del Agent Bot |
| `CHATWOOT_BOT_USER_ID` | ID del bot-user |
| `GOOGLE_CLIENT_ID` | De las credenciales OAuth descargadas |
| `GOOGLE_CLIENT_SECRET` | De las credenciales OAuth descargadas |
| `GOOGLE_REFRESH_TOKEN` | Del paso 5 |
| `GOOGLE_CALENDAR_ID` | `primary` |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_SERVICE_KEY` | Service role key de Supabase |
| `CLINIC_PHONE_HUMAN` | `+34677523665` |
| `TIMEZONE` | `Europe/Madrid` |
| `SLOT_DURATION_MINUTES` | `30` |
| `WORKING_HOURS_START` | `09:00` |
| `WORKING_HOURS_END` | `20:00` |
| `WORKING_DAYS` | `1,2,3,4` |
| `INTERNAL_API_TOKEN` | Cualquier texto aleatorio largo |
| `LOG_LEVEL` | `INFO` |

### 7.5 Actualizar la URL del Agent Bot

Ahora que tienes la URL del bot, actualiza el Agent Bot en Chatwoot:
**Settings → Integrations → Agent Bots → PDV Agent → editar** → pon la URL correcta.

---

## Paso 8 — Cron de recordatorios en Railway

1. Railway → servicio `pdv-agent` → **Settings → Cron Jobs → Add Cron Job**.
2. Configura:
   - **Schedule:** `0 * * * *` (cada hora, en punto)
   - **Command:**
     ```bash
     curl -X POST -H "X-Internal-Token: $INTERNAL_API_TOKEN" $RAILWAY_PUBLIC_DOMAIN/internal/run-reminders
     ```

---

## Paso 9 — Cargar las FAQs

Con todo desplegado, ejecuta desde tu ordenador:
```bash
cd pdv-agent
pip install supabase python-dotenv
cp .env.example .env
# Rellena SUPABASE_URL y SUPABASE_SERVICE_KEY en el .env
python scripts/seed_faqs.py
```

---

## Paso 10 — Instalar Chatwoot en los móviles del equipo

1. Descarga la app **Chatwoot** (App Store / Google Play).
2. **Instance URL:** `https://chatwoot-pdv.up.railway.app`
3. Login con el email y contraseña de cada persona.
4. Activa notificaciones push.

Para añadir más personas al equipo: Chatwoot → **Settings → Agents → Invite Agent**.

---

## Paso 11 — Prueba final

1. Envía "hola" desde un móvil al `677 523 665`.
2. El mensaje debe aparecer en Chatwoot (web y app móvil).
3. El bot debe responder en segundos con un saludo.
4. Prueba pedir una cita: el bot debe preguntar nombre, motivo y preferencia de horario.
5. Prueba que la cita aparece en Google Calendar.

---

## Mantenimiento (mensual)

- **Añadir FAQs:** Supabase → Table Editor → faqs → Insert Row.
- **Ver conversaciones:** Chatwoot web o app móvil.
- **Desactivar el bot temporalmente:** Chatwoot → Inboxes → Bot Configuration → ninguno.
- **Actualizar Chatwoot:** Railway → servicio chatwoot → Deploy → redeploy (tarda ~2 min).
- **Ver logs del bot:** Railway → servicio pdv-agent → Logs.

---

## Qué tiene que hacer sí o sí el equipo de la clínica

1. Verificar el número WhatsApp con Meta (puede tardar 1-3 días).
2. Crear las cuentas de los pasos anteriores.
3. Aprobar la plantilla de recordatorio en Meta (24-48h).
4. Decidir los precios orientativos y horario exacto para las FAQs.
5. **Mantener el Google Calendar actualizado:** las citas que entran por teléfono también deben añadirse al calendario, si no el bot ofrecerá esos huecos como disponibles.
6. Instalar Chatwoot en los móviles del equipo y aprender 5 acciones básicas.

Todo lo demás — código, respuestas, reservas, recordatorios — es automático.