"""FastAPI web interface for Travel Trend Detector pipeline."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from queue import Queue, Empty

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.config import CONFIG_DIR, PROJECT_ROOT, REPORTS_DIR
from src.utils.log_stream import PipelineLogger

WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Travel Trend Detector")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    market: str
    week: str
    selected_queries: dict[str, list[str]]
    skip_instagram: bool = True


# ---------------------------------------------------------------------------
# Shared pipeline state
# ---------------------------------------------------------------------------
_pipeline_running = False
_message_queue: Queue[str] | None = None


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(name="index.html", request=request)


@app.get("/api/markets")
async def list_markets():
    markets = []
    for p in sorted(CONFIG_DIR.glob("*.yaml")):
        with open(p) as f:
            raw = yaml.safe_load(f)
        m = raw["market"]
        markets.append({
            "code": m["code"].lower(),
            "name": m["country_name"],
        })
    return markets


@app.get("/api/markets/{code}")
async def get_market(code: str):
    config_path = CONFIG_DIR / f"{code.lower()}.yaml"
    if not config_path.exists():
        return {"error": "Market not found"}, 404
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    m = raw["market"]
    return {
        "code": m["code"].lower(),
        "name": m["country_name"],
        "language": m["language"],
        "seed_queries": raw["seed_queries"],
        "google_search_templates": raw["google_search_templates"],
    }


@app.post("/api/run")
async def start_run(body: RunRequest):
    global _pipeline_running, _message_queue

    if _pipeline_running:
        return {"error": "Pipeline is already running"}

    # Create a plain thread-safe queue — no asyncio involved on the producer side
    _message_queue = Queue()
    _pipeline_running = True

    pl = PipelineLogger(queue=_message_queue)

    def _run():
        global _pipeline_running
        try:
            from src.main import run_pipeline

            run_pipeline(
                market=body.market,
                week=body.week,
                skip_instagram=body.skip_instagram,
                selected_queries=body.selected_queries,
                log=pl,
            )
        except Exception as exc:
            pl.error(str(exc))
        finally:
            pl.finish()
            _pipeline_running = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"status": "started"}


@app.get("/api/run/stream")
async def run_stream():
    queue = _message_queue

    if queue is None:
        async def _empty():
            yield {"event": "error", "data": "No pipeline running"}
        return EventSourceResponse(_empty())

    async def event_generator():
        empty_cycles = 0
        while True:
            # Drain all available messages before yielding control
            found = False
            while True:
                try:
                    msg = queue.get_nowait()
                except Empty:
                    break

                found = True
                empty_cycles = 0

                if msg.startswith("__DONE__"):
                    report_dir = msg.removeprefix("__DONE__")
                    yield {"event": "done", "data": report_dir}
                    return
                elif msg.startswith("__ERROR__"):
                    error = msg.removeprefix("__ERROR__")
                    yield {"event": "error", "data": error}
                    continue
                elif msg == "__END__":
                    return
                else:
                    yield {"event": "log", "data": msg}

            if not found:
                empty_cycles += 1
                # Send ping every ~2s (20 cycles × 0.1s) to keep connection alive
                if empty_cycles % 20 == 0:
                    yield {"event": "ping", "data": ""}
                await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator(), ping=0)


@app.post("/api/open-finder")
async def open_finder(body: dict):
    import subprocess

    report_path = Path(body.get("path", ""))
    if report_path.exists():
        subprocess.Popen(["open", str(report_path)])
        return {"status": "opened"}
    return {"error": "Report not found"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting TTD Web UI — http://localhost:8000")
    print(f"Project root: {PROJECT_ROOT}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
