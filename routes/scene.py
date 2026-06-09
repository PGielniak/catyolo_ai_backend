import configparser

from pydantic import BaseModel, Field, UUID4
from typing import Optional
from uuid import uuid4
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, status
import logging
from models.scene import CameraFrame, RedZone
from dataclasses import asdict
from database.sqlite import SqliteDatabase
from services.scene_service import SceneService

router = APIRouter()

@dataclass
class SceneRouteConfig:
    logger: logging.Logger
    scene_service: SceneService

route_config: SceneRouteConfig = None

def get_scene_route_config():
    return route_config

def red_zones_from_dict(red_zones_data: list[dict]) -> list[RedZone]:
    """Convert dictionary-based red zones back to RedZone objects"""
    if not red_zones_data:
        return []
    return [RedZone(**zone_dict) for zone_dict in red_zones_data]

class SceneCreateUpdateRequest(BaseModel):
    scene_name: str = Field(min_length=1, max_length=255)
    camera_ip_address: str = Field(min_length=1, max_length=255)
    camera_port: int = Field(ge=1, le=65535)
    camera_username: Optional[str] = None
    camera_password: Optional[str] = None
    image: CameraFrame
    red_zones: list[RedZone] = []
    scene_prompt: Optional[str] = None
    scene_prompt_interval: Optional[int] = None
    scene_prompt_action_ids: Optional[list[UUID4]] = None

class SceneDeleteRequest(BaseModel):
    scene_id: UUID4

class SceneGetRequest(BaseModel):
    scene_id: UUID4


class SceneResponse(BaseModel):
    scene_id: UUID4 = Field(default_factory=lambda: uuid4())
    scene_name: str = Field(min_length=1, max_length=255)
    camera_ip_address: str = Field(min_length=1, max_length=255)
    camera_port: int = Field(ge=1, le=65535)
    camera_username: Optional[str] = None
    camera_password: Optional[str] = None
    image: CameraFrame
    red_zones: list[RedZone] = []
    scene_prompt: Optional[str] = None
    scene_prompt_interval: Optional[int] = None
    scene_prompt_action_ids: Optional[list[UUID4]] = None
    version: int = 0


@router.get("/")
def list_scenes(config: SceneRouteConfig = Depends(get_scene_route_config)) -> list[SceneResponse]:
    config.logger.info("Received request to list scenes")
    scenes = config.scene_service.get_all_scenes()
    if scenes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scenes found")

    def map_scene(scene):
        # Convert dictionary-based red zones back to RedZone objects
        red_zones_objects = red_zones_from_dict(scene.red_zones) if scene.red_zones else []
        return SceneResponse(scene_id=scene.scene_id,
                           scene_name=scene.scene_name,
                           camera_ip_address=scene.camera_ip_address,
                           camera_port=scene.camera_port,
                           camera_username=scene.camera_username,
                           camera_password=scene.camera_password,
                           image=CameraFrame(image=scene.image),
                           red_zones=red_zones_objects,
                           scene_prompt=scene.scene_prompt,
                           scene_prompt_interval=scene.scene_prompt_interval,
                           scene_prompt_action_ids=scene.scene_prompt_action_ids,
                           version=scene.version or 0)

    mapped_scenes = list(map(map_scene, scenes))
    return mapped_scenes

@router.get("/version")
def get_scenes_version(config: SceneRouteConfig = Depends(get_scene_route_config)):
    """Return the highest version across all scenes. Used by the worker to detect
    that the backend scene config has changed and needs to be reloaded."""
    config.logger.info("Received request for scenes version")
    scenes = config.scene_service.get_all_scenes()
    max_version = 0
    if scenes:
        max_version = max((s.version or 0) for s in scenes)
    return {"version": max_version}

@router.get("/{scene_id}")
def get_scene(scene_id: UUID4, config: SceneRouteConfig = Depends(get_scene_route_config)) -> SceneResponse:
    config.logger.info(f"Received request to get scene with id: {scene_id}")
    scene = config.scene_service.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    # Convert dictionary-based red zones back to RedZone objects
    red_zones_objects = red_zones_from_dict(scene.red_zones) if scene.red_zones else []

    mapped_scene = SceneResponse(scene_id=scene.scene_id,
                                 scene_name=scene.scene_name,
                                 camera_ip_address=scene.camera_ip_address,
                                 camera_port=scene.camera_port,
                                 camera_username=scene.camera_username,
                                 camera_password=scene.camera_password,
                                 image=CameraFrame(image=scene.image),
                                 red_zones=red_zones_objects,
                                 scene_prompt=scene.scene_prompt,
                                 scene_prompt_interval=scene.scene_prompt_interval,
                                 scene_prompt_action_ids=scene.scene_prompt_action_ids,
                                 version=scene.version or 0)
    return mapped_scene

@router.post("/create")
def create_scene(scene_request: SceneCreateUpdateRequest, config: SceneRouteConfig = Depends(get_scene_route_config)) -> SceneResponse:
    config.logger.info(f"Received request to create scene: {scene_request}")
    try:
        scene = config.scene_service.create_scene(
            scene_name=scene_request.scene_name,
            camera_ip_address=scene_request.camera_ip_address,
            camera_port=scene_request.camera_port,
            camera_username=scene_request.camera_username,
            camera_password=scene_request.camera_password,
            image=scene_request.image.image,
            red_zones=scene_request.red_zones,
            scene_prompt=scene_request.scene_prompt,
            scene_prompt_interval=scene_request.scene_prompt_interval,
            scene_prompt_action_ids=scene_request.scene_prompt_action_ids
        )
    except Exception as e:
        message = f"Failed to create scene: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    # Convert dictionary-based red zones back to RedZone objects for response
    red_zones_objects = red_zones_from_dict(scene.red_zones) if scene.red_zones else []

    mapped_scene = SceneResponse(
        scene_id=scene.scene_id,
        scene_name=scene.scene_name,
        camera_ip_address=scene.camera_ip_address,
        camera_port=scene.camera_port,
        camera_username=scene.camera_username,
        camera_password=scene.camera_password,
        image=CameraFrame(image=scene.image),
        red_zones=red_zones_objects,
        scene_prompt=scene.scene_prompt,
        scene_prompt_interval=scene.scene_prompt_interval,
        scene_prompt_action_ids=scene.scene_prompt_action_ids,
        version=scene.version or 0
    )
    return mapped_scene

@router.patch("/update/{scene_id}")
def update_scene(scene_id: UUID4, scene_request: SceneCreateUpdateRequest, config: SceneRouteConfig = Depends(get_scene_route_config)):
    config.logger.info(f"Received request to update scene: {scene_request}")
    try:
        scene = config.scene_service.get_scene(scene_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update scene: {str(e)}")
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    updated_scene = config.scene_service.update_scene(scene_id,
                                             scene_request.scene_name,
                                             scene_request.camera_ip_address,
                                             scene_request.camera_port,
                                             scene_request.image.image,
                                             scene_request.red_zones,
                                             camera_username=scene_request.camera_username,
                                             camera_password=scene_request.camera_password,
                                             scene_prompt=scene_request.scene_prompt,
                                             scene_prompt_interval=scene_request.scene_prompt_interval,
                                             scene_prompt_action_ids=scene_request.scene_prompt_action_ids)

    # Convert dictionary-based red zones back to RedZone objects for response
    red_zones_objects = red_zones_from_dict(updated_scene.red_zones) if updated_scene.red_zones else []

    mapped_scene =  SceneResponse(scene_id=updated_scene.scene_id,
                                  scene_name=updated_scene.scene_name,
                                  camera_ip_address=updated_scene.camera_ip_address,
                                  camera_port=updated_scene.camera_port,
                                  camera_username=updated_scene.camera_username,
                                  camera_password=updated_scene.camera_password,
                                  image=CameraFrame(image=updated_scene.image),
                                  red_zones=red_zones_objects,
                                  scene_prompt=updated_scene.scene_prompt,
                                  scene_prompt_interval=updated_scene.scene_prompt_interval,
                                  scene_prompt_action_ids=updated_scene.scene_prompt_action_ids,
                                  version=updated_scene.version or 0)
    return mapped_scene

@router.delete("/delete/{scene_id}")
def delete_scene(scene_id: UUID4, config: SceneRouteConfig = Depends(get_scene_route_config)):
    config.logger.info(f"Received request to delete scene with id: {scene_id}")
    try:
        config.scene_service.delete_scene(scene_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete scene: {str(e)}")
    return True

@router.get("/analyze/{scene_id}")
def analyze_scene(scene_id: UUID4, config: SceneRouteConfig = Depends(get_scene_route_config)):
    try:
        message = config.scene_service.analyze_scene(scene_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to analyze scene: {str(e)}")
    return {"message": f"{message}"}