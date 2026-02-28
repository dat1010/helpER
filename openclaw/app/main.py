import logging
import os

from fastapi import FastAPI

from .config import Config
from .engine import Engine
from .github_client import GitHubClient
from .metrics import Metrics
from .plane_client import PlaneClient

cfg = Config.from_env()
metrics = Metrics()

logging.basicConfig(
    level=getattr(logging, cfg.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("openclaw")

app = FastAPI(title="OpenClaw", version="0.1.0")

startup_errors = cfg.validate()
if startup_errors:
    log.warning("OpenClaw config warnings: %s", startup_errors)

plane = PlaneClient(cfg.plane_base_url, cfg.plane_api_token, cfg.plane_workspace_slug)
github = GitHubClient(cfg.github_token)
engine = Engine(cfg, plane, github, metrics)


@app.on_event("startup")
def startup() -> None:
    engine.start()


@app.on_event("shutdown")
def shutdown() -> None:
    engine.stop()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "openclaw",
        "pid": os.getpid(),
        "config_errors": startup_errors,
    }


@app.get("/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()


@app.get("/state")
def get_state() -> dict:
    return engine.state()
