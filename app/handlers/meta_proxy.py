import hashlib
import hmac
import json
import logging
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


def _summarize_payload(payload: dict) -> dict:
    out = {"object": payload.get("object"), "entries": []}
    for entry in payload.get("entry", []) or []:
        e = {"id": entry.get("id"), "changes": []}
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            metadata = value.get("metadata", {}) or {}
            msgs = value.get("messages", []) or []
            statuses = value.get("statuses", []) or []
            e["changes"].append({
                "field": change.get("field"),
                "phone_id": metadata.get("phone_number_id"),
                "display_phone": metadata.get("display_phone_number"),
                "messages": [
                    {"from": m.get("from"), "id": m.get("id"), "type": m.get("type")}
                    for m in msgs
                ],
                "statuses": [
                    {"id": s.get("id"), "status": s.get("status"), "recipient": s.get("recipient_id")}
                    for s in statuses
                ],
            })
        out["entries"].append(e)
    return out


async def _forward_to_chatwoot(raw_body: bytes, headers: dict) -> None:
    s = get_settings()
    if not s.meta_proxy_forward_url:
        logger.info("META-PROXY forward: SKIPPED (no forward_url configured)")
        return

    fwd_headers = {
        "Content-Type": headers.get("content-type", "application/json"),
    }
    sig = headers.get("x-hub-signature-256")
    if sig:
        fwd_headers["X-Hub-Signature-256"] = sig
    sig1 = headers.get("x-hub-signature")
    if sig1:
        fwd_headers["X-Hub-Signature"] = sig1

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(s.meta_proxy_forward_url, content=raw_body, headers=fwd_headers)
        dt_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "META-PROXY forward: status=%s ms=%s url=%s body_preview=%s",
            resp.status_code, dt_ms, s.meta_proxy_forward_url, resp.text[:200],
        )
    except Exception as e:
        dt_ms = int((time.monotonic() - t0) * 1000)
        logger.exception("META-PROXY forward: FAILED ms=%s err=%s", dt_ms, e)


@router.get("/webhook/meta")
async def meta_verify(request: Request):
    s = get_settings()
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    logger.info("META-PROXY verify: mode=%s token_match=%s", mode, token == s.meta_proxy_verify_token)

    if mode == "subscribe" and token == s.meta_proxy_verify_token and challenge:
        return PlainTextResponse(challenge, status_code=200)
    return PlainTextResponse("forbidden", status_code=403)


@router.post("/webhook/meta")
async def meta_delivery(request: Request):
    s = get_settings()
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    sig = headers.get("x-hub-signature-256")

    sig_ok = False
    if s.meta_proxy_app_secret:
        sig_ok = _verify_signature(raw_body, sig, s.meta_proxy_app_secret)

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    summary = _summarize_payload(payload) if isinstance(payload, dict) else {}

    logger.info(
        "META-PROXY recv: bytes=%d sig_present=%s sig_ok=%s summary=%s",
        len(raw_body), bool(sig), sig_ok, json.dumps(summary, ensure_ascii=False),
    )
    logger.info("META-PROXY recv full payload: %s", raw_body.decode("utf-8", errors="replace"))

    await _forward_to_chatwoot(raw_body, headers)

    return JSONResponse({"status": "ok"})
