import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import cv2
from fastapi import APIRouter, HTTPException, status, Depends
from dependencies.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])


@dataclass
class FrameRouteConfig:
    logger: logging.Logger
    database: object  # SqliteDatabase — avoid circular import


route_config: FrameRouteConfig = None


def get_frame_route_config():
    return route_config


def _grab_frame(camera_ip: str, camera_port: int, username: str, password: str) -> bytes:
    rtsp_url = f'rtsp://{username}:{password}@{camera_ip}:{camera_port}/stream1'

    os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        raise RuntimeError(f'Could not open RTSP stream at {camera_ip}:{camera_port}')

    try:
        ret, frame = cap.read()
        if not ret or frame is None:
            raise RuntimeError('Connected to stream but could not read a frame')
        ok, buf = cv2.imencode('.jpg', frame)
        if not ok:
            raise RuntimeError('Failed to encode frame as JPEG')
        return buf.tobytes()
    finally:
        cap.release()


@router.get('/')
def get_frame(
    camera_ip: str,
    camera_port: int,
    scene_id: Optional[str] = None,
    camera_username: Optional[str] = None,
    camera_password: Optional[str] = None,
):
    cfg = get_frame_route_config()
    cfg.logger.info(f'Frame requested for {camera_ip}:{camera_port}')

    raw_password = camera_password or ''
    raw_username = camera_username or ''

    # If no password supplied, look it up from the scene record
    if not raw_password and scene_id:
        scene = cfg.database.get_scene(scene_id)
        if scene:
            raw_password = scene.camera_password or ''
            if not raw_username:
                raw_username = scene.camera_username or ''

    if not raw_password:
        raw_password = os.getenv('CAMERA_PASSWORD', '')
    if not raw_username:
        raw_username = os.getenv('CAMERA_USERNAME', '')

    username = quote(raw_username, safe='')
    password = quote(raw_password, safe='')

    try:
        jpeg_bytes = _grab_frame(camera_ip, camera_port, username, password)
    except RuntimeError as exc:
        cfg.logger.error(f'Frame grab failed: {exc}')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        cfg.logger.exception('Unexpected error grabbing frame')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {'image': base64.b64encode(jpeg_bytes).decode()}
