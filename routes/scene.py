import configparser
import os

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
from dependencies.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])

# Upper bound on the number of scenes (cameras) the worker is expected to
# serve concurrently. Enforced on create so the contract is explicit at the
# source of truth rather than only as a worker-side safety net.
MAX_SCENES = int(os.getenv("MAX_SCENES", "3"))


@dataclass
class SceneRouteConfig:
    logger: logging.Logger
    scene_service: SceneService


route_config: SceneRouteConfig = None


def get_scene_route_config():
    return route_config


def red_zones_from_dict(red_zones_data: list[dict]) -> list[RedZone]:
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
    global_detection_enabled: bool = False
    global_detection_classes: Optional[list[str]] = None
    global_detection_action_ids: Optional[list[UUID4]] = None
    global_detection_cooldown_seconds: Optional[int] = 60


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
    camera_password: Optional[str] = None  # always empty in responses
    image: CameraFrame
    red_zones: list[RedZone] = []
    scene_prompt: Optional[str] = None
    scene_prompt_interval: Optional[int] = None
    scene_prompt_action_ids: Optional[list[UUID4]] = None
    global_detection_enabled: bool = False
    global_detection_classes: Optional[list[str]] = None
    global_detection_action_ids: Optional[list[UUID4]] = None
    global_detection_cooldown_seconds: Optional[int] = 60
    version: int = 0


def _map_scene(scene, redact: bool = True) -> SceneResponse:
    red_zones_objects = red_zones_from_dict(scene.red_zones) if scene.red_zones else []
    return SceneResponse(
        scene_id=scene.scene_id,
        scene_name=scene.scene_name,
        camera_ip_address=scene.camera_ip_address,
        camera_port=scene.camera_port,
        camera_username=scene.camera_username,
        camera_password="" if redact else (scene.camera_password or ""),  # write-only unless internal caller
        image=CameraFrame(image=scene.image),
        red_zones=red_zones_objects,
        scene_prompt=scene.scene_prompt,
        scene_prompt_interval=scene.scene_prompt_interval,
        scene_prompt_action_ids=scene.scene_prompt_action_ids,
        global_detection_enabled=bool(scene.global_detection_enabled),
        global_detection_classes=scene.global_detection_classes or [],
        global_detection_action_ids=scene.global_detection_action_ids or [],
        global_detection_cooldown_seconds=scene.global_detection_cooldown_seconds or 60,
        version=scene.version or 0,
    )


@router.get("/")
def list_scenes(config: SceneRouteConfig = Depends(get_scene_route_config)) -> list[SceneResponse]:
    config.logger.info("Received request to list scenes")
    scenes = config.scene_service.get_all_scenes()
    if scenes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scenes found")
    return [_map_scene(s) for s in scenes]


@router.get("/version")
def get_scenes_version(config: SceneRouteConfig = Depends(get_scene_route_config)):
    config.logger.info("Received request for scenes version")
    scenes = config.scene_service.get_all_scenes()
    max_version = 0
    per_scene = []
    if scenes:
        max_version = max((s.version or 0) for s in scenes)
        per_scene = [{"scene_id": s.scene_id, "version": s.version or 0} for s in scenes]
    # `version` (global max) is kept for backward compatibility with the
    # legacy single-camera worker; `scenes` carries per-scene versions used
    # by the multi-camera worker's per-scene diff.
    return {"version": max_version, "scenes": per_scene}


# Must be declared before /{scene_id} to prevent "internal" matching as a UUID.
@router.get("/internal/")
def list_scenes_internal(config: SceneRouteConfig = Depends(get_scene_route_config)) -> list[SceneResponse]:
    """Full scene configs including camera credentials — for worker use only.

    Mirrors /action/internal/: the worker needs camera_password to build the
    RTSP URL now that credentials are redacted on the public /scene/ read
    (WS4). Gated by the same require_api_key dependency as every route.
    """
    config.logger.info("Received request to list scenes (internal)")
    scenes = config.scene_service.get_all_scenes()
    if scenes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scenes found")
    return [_map_scene(s, redact=False) for s in scenes]


@router.get("/{scene_id}")
def get_scene(scene_id: UUID4, config: SceneRouteConfig = Depends(get_scene_route_config)) -> SceneResponse:
    config.logger.info(f"Received request to get scene with id: {scene_id}")
    scene = config.scene_service.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    return _map_scene(scene)


@router.post("/create")
def create_scene(scene_request: SceneCreateUpdateRequest, config: SceneRouteConfig = Depends(get_scene_route_config)) -> SceneResponse:
    config.logger.info(f"Received request to create scene: {scene_request}")
    existing = config.scene_service.get_all_scenes()
    if existing is not None and len(existing) >= MAX_SCENES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum number of scenes ({MAX_SCENES}) reached. "
                   f"Delete an existing scene before creating a new one.",
        )
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
            scene_prompt_action_ids=scene_request.scene_prompt_action_ids,
            global_detection_enabled=scene_request.global_detection_enabled,
            global_detection_classes=scene_request.global_detection_classes,
            global_detection_action_ids=scene_request.global_detection_action_ids,
            global_detection_cooldown_seconds=scene_request.global_detection_cooldown_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create scene: {e}")
    return _map_scene(scene)


@router.patch("/update/{scene_id}")
def update_scene(scene_id: UUID4, scene_request: SceneCreateUpdateRequest, config: SceneRouteConfig = Depends(get_scene_route_config)):
    config.logger.info(f"Received request to update scene: {scene_request}")
    try:
        scene = config.scene_service.get_scene(scene_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update scene: {str(e)}")
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    updated_scene = config.scene_service.update_scene(
        scene_id,
        scene_request.scene_name,
        scene_request.camera_ip_address,
        scene_request.camera_port,
        scene_request.image.image,
        scene_request.red_zones,
        camera_username=scene_request.camera_username,
        camera_password=scene_request.camera_password,
        scene_prompt=scene_request.scene_prompt,
        scene_prompt_interval=scene_request.scene_prompt_interval,
        scene_prompt_action_ids=scene_request.scene_prompt_action_ids,
        global_detection_enabled=scene_request.global_detection_enabled,
        global_detection_classes=scene_request.global_detection_classes,
        global_detection_action_ids=scene_request.global_detection_action_ids,
        global_detection_cooldown_seconds=scene_request.global_detection_cooldown_seconds,
    )
    return _map_scene(updated_scene)


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
