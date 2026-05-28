import os

import uvicorn
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
import logging
from logging.handlers import RotatingFileHandler
from services.api_key_validation_service import ApiKeyValidationService, ApiKeyValidationRequest
from dotenv import load_dotenv
from routes import api_key, scene, action, log, frame
from services.api_key_validation_service import ApiKeyValidationService
from services.scene_service import SceneService
from services.action_service import ActionService
from services.log_service import LogService
from pathlib import Path

from database.sqlite import SqliteDatabase

# COMMON
load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("catyolo_backend")
# Configure file logging with timestamps and log levels
log_file = Path(os.getenv("LOG_FILE_PATH"))
log_dir = log_file.parent
os.makedirs(log_dir, exist_ok=True)
handler = RotatingFileHandler(os.getenv("LOG_FILE_PATH"), maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
database = SqliteDatabase(os.getenv("DATABASE_PATH"))


#
# place holder for running the app
#

# API
api_key.route_config = api_key.ApiKeyRouteConfig(logger=logger, api_key_validation_service=ApiKeyValidationService())
# Create tables
database.create_tables()
database.migrate()
scene.route_config = scene.SceneRouteConfig(logger=logger, scene_service=SceneService(database))
action.route_config = action.ActionRouteConfig(logger=logger, action_service=ActionService(database))
log.route_config = log.LogRouteConfig(logger=logger, log_service=LogService(logger))
frame.route_config = frame.FrameRouteConfig(logger=logger)


app = FastAPI()
app.include_router(api_key.router, prefix="/api_key", tags=["api_key"])
app.include_router(scene.router, prefix="/scene", tags=["scene"])
app.include_router(action.router, prefix="/action", tags=["action"])
app.include_router(log.router, prefix="/log", tags=["log"])
app.include_router(frame.router, prefix="/frame", tags=["frame"])



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)