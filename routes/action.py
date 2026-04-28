from pydantic import BaseModel, Field, UUID4
from typing import Optional
from uuid import uuid4
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from database.sqlite import SqliteDatabase
from services.action_service import ActionService

router = APIRouter()

@dataclass
class ActionRouteConfig:
    logger: logging.Logger
    action_service: ActionService

route_config: ActionRouteConfig = None

def get_action_route_config():
    return route_config

class ActionCreateUpdateRequest(BaseModel):
    action_name: str = Field(min_length=1, max_length=255)
    action_type: str = Field(min_length=1, max_length=255)
    action_config: dict = Field(default_factory=dict)

class ActionDeleteRequest(BaseModel):
    action_id: UUID4

class ActionGetRequest(BaseModel):
    action_id: UUID4


class ActionResponse(BaseModel):
    action_id: UUID4 = Field(default_factory=lambda: uuid4())
    action_name: str = Field(min_length=1, max_length=255)
    action_type: str = Field(min_length=1, max_length=255)
    action_config: dict = Field(default_factory=dict)


@router.get("/")
def list_actions(config: ActionRouteConfig = Depends(get_action_route_config)) -> list[ActionResponse]:
    config.logger.info("Received request to list actions")
    actions = config.action_service.get_all_actions()
    if actions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No actions found")
    mapped_actions = list(map(lambda action: ActionResponse(action_id=action.action_id,
                                                          action_name=action.action_name,
                                                          action_type=action.action_type,
                                                          action_config=action.action_config),
        actions))
    return mapped_actions

@router.get("/{action_id}")
def get_action(action_id: UUID4, config: ActionRouteConfig = Depends(get_action_route_config)) -> ActionResponse:
    config.logger.info(f"Received request to get action with id: {action_id}")
    action = config.action_service.get_action(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    mapped_action = ActionResponse(action_id=action.action_id,
                                  action_name=action.action_name,
                                  action_type=action.action_type,
                                  action_config=action.action_config)
    return mapped_action

@router.post("/create")
def create_action(action_request: ActionCreateUpdateRequest, config: ActionRouteConfig = Depends(get_action_route_config)) -> ActionResponse:
    config.logger.info(f"Received request to create action: {action_request}")
    try:
        action = config.action_service.create_action(
            action_name=action_request.action_name,
            action_type=action_request.action_type,
            action_config=action_request.action_config
        )
    except Exception as e:
        message = f"Failed to create action: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)
    mapped_action = ActionResponse(
        action_id=action.action_id,
        action_name=action.action_name,
        action_type=action.action_type,
        action_config=action.action_config
    )
    return mapped_action

@router.patch("/update/{action_id}")
def update_action(action_id: UUID4,action_request: ActionCreateUpdateRequest, config: ActionRouteConfig = Depends(get_action_route_config)):
    config.logger.info(f"Received request to update action: {action_request}")
    try:
        action = config.action_service.get_action(action_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update action")
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")

    updated_action = config.action_service.update_action(action_id,
                                             action_request.action_name,
                                             action_request.action_type,
                                             action_request.action_config)
    mapped_action =  ActionResponse(action_id=updated_action.action_id,
                                  action_name=updated_action.action_name,
                                  action_type=updated_action.action_type,
                                  action_config=updated_action.action_config)
    return mapped_action

@router.delete("/delete/{action_id}")
def delete_action(action_id: UUID4, config: ActionRouteConfig = Depends(get_action_route_config)):
    config.logger.info(f"Received request to delete action with id: {action_id}")
    try:
        config.action_service.delete_action(action_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete action: {str(e)}")
    return {"message": "Action deleted successfully"}