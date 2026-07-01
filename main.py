import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import api_key, scene, action, log, frame
from services.api_key_service import ApiKeyService
from services.scene_service import SceneService
from services.action_service import ActionService
from services.log_service import LogService
from dependencies.auth import init_auth
from database.sqlite import SqliteDatabase

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("catyolo_backend")

log_file = os.getenv("LOG_FILE_PATH")
if log_file:
    log_dir = Path(log_file).parent
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# ── Database ───────────────────────────────────────────────────────────────
database = SqliteDatabase(os.getenv("DATABASE_PATH"))
database.create_tables()
database.migrate()

# ── Auth ───────────────────────────────────────────────────────────────────
api_key_service = ApiKeyService(database)
init_auth(api_key_service)

if not api_key_service.has_any_key():
    logger.warning(
        "No API keys found in database. "
        "Create one with: uv run python scripts/create_api_key.py"
    )

# ── Route configs ──────────────────────────────────────────────────────────
api_key.route_config = api_key.ApiKeyRouteConfig(logger=logger, api_key_service=api_key_service)
scene.route_config = scene.SceneRouteConfig(logger=logger, scene_service=SceneService(database))
action.route_config = action.ActionRouteConfig(logger=logger, action_service=ActionService(database))
log.route_config = log.LogRouteConfig(logger=logger, log_service=LogService(logger))
frame.route_config = frame.FrameRouteConfig(logger=logger, database=database)

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI()

cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3100").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_key.router, prefix="/api_key", tags=["api_key"])
app.include_router(scene.router, prefix="/scene", tags=["scene"])
app.include_router(action.router, prefix="/action", tags=["action"])
app.include_router(log.router, prefix="/log", tags=["log"])
app.include_router(frame.router, prefix="/frame", tags=["frame"])


@app.get("/healthz", tags=["health"])
def healthz():
    try:
        database.get_all_scenes()
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Healthz DB check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
