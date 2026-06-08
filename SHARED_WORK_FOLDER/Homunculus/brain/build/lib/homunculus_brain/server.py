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
from . import calendar as cal
from . import intent_router
from . import llm
from .config import load_config
from .schemas import (
    CaptureRequest,
    CaptureResponse,
    HealthResponse,
    ParsedIntent,
)


log = logging.getLogger(__name__)


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
        now = req.captured_at or datetime.now(ZoneInfo(config.default_tz_name))
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(config.default_tz_name))

        intent = await llm.parse_intent(
            req.text,
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
        return intent_router.route(intent, config=config, now=now)

    class ConfirmRequest(BaseModel):
        intent: ParsedIntent
        captured_at: Optional[datetime] = None

    @app.post("/capture/confirm", response_model=CaptureResponse)
    async def capture_confirm(req: ConfirmRequest) -> CaptureResponse:
        now = req.captured_at or datetime.now(ZoneInfo(config.default_tz_name))
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(config.default_tz_name))
        return intent_router.commit_calendar_event(req.intent, config=config, now=now)

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
