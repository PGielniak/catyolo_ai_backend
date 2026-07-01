from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from services.api_key_service import ApiKeyService
import logging
from dataclasses import dataclass

router = APIRouter()


@dataclass
class ApiKeyRouteConfig:
    logger: logging.Logger
    api_key_service: ApiKeyService


route_config: ApiKeyRouteConfig = None


def get_api_key_route_config():
    return route_config


class ValidateKeyRequest(BaseModel):
    raw_key: str


@router.post("/validate")
def validate_api_key(req: ValidateKeyRequest, config: ApiKeyRouteConfig = Depends(get_api_key_route_config)):
    is_valid = config.api_key_service.validate(req.raw_key)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return {"message": "API key is valid"}
