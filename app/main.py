import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.handlers.webhook import verify_chatwoot_webhook, extract_message_data
from app.handlers.conversation import handle_incoming_message
from app.handlers.reminders import run_reminders
from app.handlers.meta_proxy import router as meta_proxy_router

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PDV Agent starting up")
    yield
    logger.info("PDV Agent shutting down")


app = FastAPI(title="PDV Agent", lifespan=lifespan)
app.include_router(meta_proxy_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pdv-agent"}


@app.post("/webhook/chatwoot")
async def chatwoot_webhook(request: Request):
    payload = await verify_chatwoot_webhook(request)
    data = extract_message_data(payload)

    if data is None:
        return JSONResponse({"status": "ignored"})

    # Fire-and-forget: respond immediately to Chatwoot, process async
    asyncio.create_task(handle_incoming_message(data))
    return JSONResponse({"status": "processing"})


@app.post("/internal/run-reminders")
async def internal_run_reminders(x_internal_token: str = Header(None)):
    s = get_settings()
    if x_internal_token != s.internal_api_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    result = await asyncio.to_thread(run_reminders)
    logger.info(f"Reminders result: {result}")
    return result