"""FastAPI server — the HTTP surface the phone client (and curl) talks to.

Defaults bind to 0.0.0.0:8765. Tailscale handles auth/transport — only
devices on the user's tailnet can reach this. There is intentionally no
endpoint-level authentication for v1; if Homunculus is ever exposed to a
larger network, add a bearer token here first.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import VERSION, DESIGN_VERSION
from . import activity_log
from . import calendar as cal
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
    ParsedIntent,
    ReminderRow,
)


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
    async def reminders_upcoming(window_hours: int = 72) -> list[ReminderRow]:
        """Return reminders the phone should register over the next window.

        Combines per-event strike rows (read from the persisted sidecars) with
        daily summary rows for the next few days. Sorted ascending by
        ``fire_at`` and capped at 60 so we stay under iOS's 64-pending limit.
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
        )
        return rows[:60]

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
