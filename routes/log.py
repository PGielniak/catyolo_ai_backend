from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from services.log_service import LogService
import logging
from dataclasses import dataclass
from dependencies.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])


@dataclass
class LogRouteConfig:
    logger: logging.Logger
    log_service: LogService


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


route_config: LogRouteConfig = None


def get_log_route_config():
    return route_config


@router.get("/get/{n_lines}")
def get_logs(n_lines: int = 100, config: LogRouteConfig = Depends(get_log_route_config)) -> list[str]:
    config.logger.debug(f"Number of logs to retrieve: {n_lines}")
    try:
        logs = config.log_service.get_logs(n_lines)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve logs: {str(e)}")
    return logs


@router.post("/set_log_level")
def set_log_level(level: LogLevel, config: LogRouteConfig = Depends(get_log_route_config)):
    level_value = level.value
    config.logger.debug(f"Setting log level to: {level_value}")
    try:
        config.log_service.set_log_level(str(level_value))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set log level: {str(e)}")
    return {"message": f"Log level set to {level_value}"}


@router.get("/get_log_level")
def get_log_level(config: LogRouteConfig = Depends(get_log_route_config)):
    current_level = config.log_service.get_log_level()
    return {"current_log_level": current_level}
