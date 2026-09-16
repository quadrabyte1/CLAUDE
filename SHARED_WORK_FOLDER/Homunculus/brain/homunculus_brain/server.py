"""FastAPI server — the HTTP surface the phone client (and curl) talks to.

Defaults bind to 0.0.0.0:8765. Tailscale handles auth/transport — only
devices on the user's tailnet can reach this. There is intentionally no
endpoint-level authentication for v1; if Homunculus is ever exposed to a
larger network, add a bearer token here first.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import VERSION, DESIGN_VERSION
from . import activity_log
from . import calendar as cal
from . import capture_parsed
from . import dashboard as dash
from . import intent_router
from . import llm
from . import reminders as rem
from .config import load_config
from .schemas import (
    AckRequest,
    AckResponse,
    CaptureRequest,
    CaptureResponse,
    HealthResponse,
    ParsedCaptureRequest,
    ParsedCaptureResponse,
    ParsedIntent,
    ReminderRow,
)
from fastapi.responses import JSONResponse


class ConfirmRequest(BaseModel):
    """Body of /capture/confirm.

    Defined at module scope (not nested inside ``create_app``) so FastAPI's
    Pydantic introspection treats it as a request body, not a query param.
    The v1.2 ``speaker_tz`` field is optional; when present it overrides
    the server default the same way ``/capture/text`` does.
    """

    intent: ParsedIntent
    captured_at: Optional[datetime] = None
    speaker_tz: Optional[str] = None


log = logging.getLogger(__name__)


def _resolve_tz(name: Optional[str], default: str) -> ZoneInfo:
    """Return a ZoneInfo for ``name`` if it parses; otherwise the default.

    Honors persona rule #4 — phone-reported zone wins over server default —
    while preserving rule "invalid TZ → fall back, don't 500."
    """
    if name:
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001 - any zoneinfo error falls back
            log.warning("unknown speaker_tz %r — falling back to default %s", name, default)
    return ZoneInfo(default)


def create_app() -> FastAPI:
    config = load_config()
    app = FastAPI(title="Homunculus brain", version=VERSION)
    app.state.config = config

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        """Return 400 for schema violations on /capture/parsed per the Sprite
        contract; keep FastAPI's default 422 elsewhere so v1.2 clients don't
        see a behavior change.
        """
        if request.url.path == "/capture/parsed":
            return JSONResponse(
                status_code=400,
                content={"stored": False, "reason": "schema_violation", "detail": exc.errors()},
            )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            design_version=DESIGN_VERSION,
            package_version=VERSION,
            vault_path=str(config.vault_path),
        )

    @app.post("/capture/text", response_model=CaptureResponse)
    async def capture_text(req: CaptureRequest) -> CaptureResponse:
        tz = _resolve_tz(req.speaker_tz, config.default_tz_name)
        now = req.captured_at or datetime.now(tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)

        intent = await llm.parse_intent(
            req.text,
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
        return intent_router.route(intent, config=config, now=now, tz=tz)

    @app.post("/capture/confirm", response_model=CaptureResponse)
    async def capture_confirm(req: ConfirmRequest) -> CaptureResponse:
        tz = _resolve_tz(req.speaker_tz, config.default_tz_name)
        now = req.captured_at or datetime.now(tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        return intent_router.commit_calendar_event(req.intent, config=config, now=now, tz=tz)

    @app.get("/events")
    async def list_events(day: Optional[str] = None) -> list[dict]:
        if day:
            try:
                target = datetime.fromisoformat(day).replace(tzinfo=ZoneInfo(config.default_tz_name))
            except ValueError as exc:
                raise HTTPException(400, f"bad day: {exc}")
            start = target.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            events = cal.list_events_between(config.vault_path, start, end)
        else:
            events = cal.list_events(config.vault_path)
        return [e.model_dump(mode="json") for e in events]

    @app.get("/reminders/upcoming", response_model=list[ReminderRow])
    async def reminders_upcoming(
        window_hours: int = 72,
        include_fired: bool = False,
    ) -> list[ReminderRow]:
        """Return reminders the phone should register over the next window.

        Combines per-event strike rows (read from the persisted sidecars) with
        daily summary rows for the next few days. Sorted ascending by
        ``fire_at`` and capped at 60 so we stay under iOS's 64-pending limit.

        ``include_fired`` is a test-client affordance (v1.2.1): when true the
        window opens to ``now - 24h`` and rows are returned regardless of
        status, so the boss can see strikes that already fired during live
        testing. The phone client should never set this.
        """
        tz = ZoneInfo(config.default_tz_name)
        now = datetime.now(tz)
        window_end = now + timedelta(hours=window_hours)

        rows = rem.collect_upcoming_rows(
            config.vault_path,
            now=now,
            window_end=window_end,
            anchor_tz=tz,
            summary_time=config.morning_summary_time,
            include_fired=include_fired,
            warnings_path=config.sprite_warnings_path,
        )
        return rows[:60]

    @app.post("/capture/parsed")
    async def capture_parsed_endpoint(req: ParsedCaptureRequest):
        """Sprite → Herman: submit a pre-parsed record for dispatch.

        Response codes:
          * 200 — dispatched (or idempotent replay of a prior dispatch).
          * 400 — schema violation (FastAPI/Pydantic auto-returns 422 by
            default; we re-raise pydantic ValidationErrors as 400 here per
            the Sprite contract; missing-field / bad-verb / bad-enum
            hit this branch).
          * 422 — confidence under Herman's floor. Body:
            ``{"stored": false, "reason": "low_confidence"}``.
        """
        tz = _resolve_tz(None, config.default_tz_name)

        if capture_parsed.below_floor(req, config=config):
            log.info(
                "capture/parsed rejected low-confidence record: %s < %s",
                req.confidence,
                config.min_capture_confidence,
            )
            return JSONResponse(
                status_code=422,
                content={"stored": False, "reason": "low_confidence"},
            )

        resp = capture_parsed.dispatch(req, config=config, tz=tz)
        return resp.model_dump(mode="json")

    @app.post("/ack", response_model=AckResponse)
    async def ack(req: AckRequest) -> AckResponse:
        """Mark a reminder acked; cancel all later strikes in the same chain.

        Idempotent — acking an already-acked row returns the same shape with
        an empty ``cancelled_kinds``. Unknown event ids return 200 with empty
        results (the brain is the source of truth; the phone reconciles on
        the next ``/reminders/upcoming`` pull).
        """
        tz = ZoneInfo(config.default_tz_name)
        acked_at = req.acked_at or datetime.now(tz)
        if acked_at.tzinfo is None:
            acked_at = acked_at.replace(tzinfo=tz)

        result = rem.ack_reminder(
            config.vault_path,
            event_id=req.event_id,
            kind=req.kind,
            acked_at=acked_at,
        )
        activity_log.log(
            config.vault_path,
            "event_ack",
            at=acked_at,
            event_id=req.event_id,
            details={
                "acked_kind": req.kind.value,
                "cancelled_kinds": [k.value for k in result.cancelled_kinds],
            },
        )
        return result

    # --- v1.5.0 dashboard -----------------------------------------------------
    # Read-only activity feed. No LLM call, no external I/O. Just JSONL read.

    @app.get("/dashboard/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_page() -> HTMLResponse:
        return HTMLResponse(content=dash.DASHBOARD_HTML, status_code=200)

    @app.get("/dashboard/data")
    async def dashboard_data(
        limit: int = Query(default=200, ge=1, le=1000),
        since: Optional[str] = None,
    ) -> dict:
        """Return activity rows reverse-chronological.

        Optional ``?since=<iso8601>`` returns only rows newer than that
        timestamp (exclusive), for incremental auto-refresh.
        ``?limit=N`` caps results; default 200, max 1000.
        """
        since_dt: Optional[datetime] = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                if since_dt.tzinfo is None:
                    from datetime import timezone as _tz
                    since_dt = since_dt.replace(tzinfo=_tz.utc)
            except ValueError:
                raise HTTPException(400, f"invalid since timestamp: {since!r}")

        rows, latest_at = dash.read_recent(
            config.vault_path,
            limit=limit,
            since=since_dt,
        )
        return {"rows": rows, "latest_at": latest_at}

    # --- v1.2.1 test client ---------------------------------------------------
    # Single-page browser harness for hand-exercising the brain end-to-end
    # without curl. Lives in homunculus_brain/test_client/ as a single
    # index.html (vanilla JS, no build step) so the brain can ship it with
    # zero extra dependencies. Mounted at /test/. The portability rule
    # holds — same code runs on Linux when the brain migrates.
    _test_client_dir = Path(__file__).resolve().parent / "test_client"
    if _test_client_dir.is_dir():
        app.mount("/test", StaticFiles(directory=str(_test_client_dir), html=True), name="test_client")

        @app.get("/test", include_in_schema=False)
        async def _test_root_redirect() -> FileResponse:
            # FastAPI's StaticFiles with html=True serves index.html on the
            # mount path WITH a trailing slash. A bare /test (no slash) gets
            # a 404 from StaticFiles, which is confusing — so handle it here.
            return FileResponse(str(_test_client_dir / "index.html"))

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = load_config()
    uvicorn.run(
        "homunculus_brain.server:create_app",
        host=cfg.server_host,
        port=cfg.server_port,
        factory=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
