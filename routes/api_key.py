from fastapi import APIRouter, Depends, HTTPException, status
from services.api_key_validation_service import ApiKeyValidationService, ApiKeyValidationRequest
from dotenv import load_dotenv
import logging
from dataclasses import dataclass
import os

router = APIRouter()

@dataclass
class ApiKeyRouteConfig:
    logger: logging.Logger
    api_key_validation_service: ApiKeyValidationService

route_config: ApiKeyRouteConfig = None

def get_api_key_route_config():
    return route_config

@router.post("/validate")
def validate_api_key(raw_key:str, config: ApiKeyRouteConfig = Depends(get_api_key_route_config)):
    config.logger.debug(f"Received raw key: {raw_key}")
    req = ApiKeyValidationRequest(raw_key=raw_key)
    is_valid = config.api_key_validation_service.validate(req)
    is_valid = True #TODO override while waiting for api-key service implementation
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return {"message": "API key is valid"}