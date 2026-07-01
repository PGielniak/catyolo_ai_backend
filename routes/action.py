from pydantic import BaseModel, Field, UUID4
from typing import Optional
from uuid import uuid4
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, status
import logging

import smbclient
import smbclient.path

from database.sqlite import SqliteDatabase
from services.action_service import ActionService
from dependencies.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])

# Keys whose values are redacted on public read (write-only semantics)
_SENSITIVE_SUFFIXES = ("Token", "Password", "Secret", "ApiKey")


def _redact_config(config: dict) -> dict:
    return {
        k: "" if any(k.endswith(s) for s in _SENSITIVE_SUFFIXES) else v
        for k, v in config.items()
    }


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


class SmbTestRequest(BaseModel):
    smb_host: str
    smb_port: int = 445
    smb_share: str
    smb_folder: str = ""
    smb_username: str
    smb_password: str
    smb_domain: str = ""


class SmbTestResponse(BaseModel):
    ok: bool
    message: str


class ActionResponse(BaseModel):
    action_id: UUID4 = Field(default_factory=lambda: uuid4())
    action_name: str = Field(min_length=1, max_length=255)
    action_type: str = Field(min_length=1, max_length=255)
    action_config: dict = Field(default_factory=dict)


def _map_action(action, redact: bool = True) -> ActionResponse:
    cfg = action.action_config or {}
    return ActionResponse(
        action_id=action.action_id,
        action_name=action.action_name,
        action_type=action.action_type,
        action_config=_redact_config(cfg) if redact else cfg,
    )


@router.get("/")
def list_actions(config: ActionRouteConfig = Depends(get_action_route_config)) -> list[ActionResponse]:
    config.logger.info("Received request to list actions")
    actions = config.action_service.get_all_actions()
    if actions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No actions found")
    return [_map_action(a, redact=True) for a in actions]


# Must be declared before /{action_id} to prevent "internal" matching as a UUID
@router.get("/internal/")
def list_actions_internal(config: ActionRouteConfig = Depends(get_action_route_config)) -> list[ActionResponse]:
    """Full action configs including sensitive credentials — for worker use only."""
    config.logger.info("Received request to list actions (internal)")
    actions = config.action_service.get_all_actions()
    if actions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No actions found")
    return [_map_action(a, redact=False) for a in actions]


@router.get("/{action_id}")
def get_action(action_id: UUID4, config: ActionRouteConfig = Depends(get_action_route_config)) -> ActionResponse:
    config.logger.info(f"Received request to get action with id: {action_id}")
    action = config.action_service.get_action(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return _map_action(action, redact=True)


@router.post("/create")
def create_action(action_request: ActionCreateUpdateRequest, config: ActionRouteConfig = Depends(get_action_route_config)) -> ActionResponse:
    config.logger.info(f"Received request to create action: {action_request}")
    try:
        action = config.action_service.create_action(
            action_name=action_request.action_name,
            action_type=action_request.action_type,
            action_config=action_request.action_config,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create action: {e}")
    return _map_action(action, redact=True)


@router.patch("/update/{action_id}")
def update_action(action_id: UUID4, action_request: ActionCreateUpdateRequest, config: ActionRouteConfig = Depends(get_action_route_config)):
    config.logger.info(f"Received request to update action: {action_request}")
    try:
        action = config.action_service.get_action(action_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update action")
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")

    updated_action = config.action_service.update_action(
        action_id,
        action_request.action_name,
        action_request.action_type,
        action_request.action_config,
    )
    return _map_action(updated_action, redact=True)


@router.post("/test-smb")
def test_smb_connection(body: SmbTestRequest) -> SmbTestResponse:
    """Upload a tiny test file to the SMB share, then delete it."""
    logging.getLogger("smbprotocol").setLevel(logging.WARNING)
    logging.getLogger("spnego").setLevel(logging.WARNING)

    username = body.smb_username
    domain = (body.smb_domain or "").strip()
    if domain and domain.upper() != "WORKGROUP":
        username = f"{domain}\\{username}"

    folder = (body.smb_folder or "").strip().replace("\\", "/").strip("/")
    test_filename = ".catyolo_connection_test"

    def unc(*parts: str) -> str:
        segments = [body.smb_host, body.smb_share] + [p.strip("/\\") for p in parts if p]
        return "\\\\" + "\\".join(segments)

    try:
        smbclient.register_session(
            body.smb_host,
            username=username,
            password=body.smb_password,
            port=body.smb_port,
            auth_protocol="negotiate",
        )

        share_path = unc()
        try:
            smbclient.listdir(share_path)
        except Exception as e:
            return SmbTestResponse(
                ok=False,
                message=f"Cannot access share '{body.smb_share}': {e}",
            )

        if folder:
            folder_path = unc(folder)
            try:
                smbclient.makedirs(folder_path, exist_ok=True)
            except Exception as e:
                return SmbTestResponse(
                    ok=False,
                    message=f"Cannot create folder '{folder}': {e}",
                )

        test_path = unc(folder, test_filename) if folder else unc(test_filename)

        with smbclient.open_file(test_path, mode="wb") as fh:
            fh.write(b"catyolo test")

        smbclient.remove(test_path)

        return SmbTestResponse(
            ok=True,
            message=f"Upload + delete ok on //{body.smb_host}/{body.smb_share}/{folder}",
        )
    except Exception as exc:
        return SmbTestResponse(ok=False, message=str(exc))
    finally:
        try:
            smbclient.reset_connection_cache()
        except Exception:
            pass


@router.delete("/delete/{action_id}")
def delete_action(action_id: UUID4, config: ActionRouteConfig = Depends(get_action_route_config)):
    config.logger.info(f"Received request to delete action with id: {action_id}")
    try:
        config.action_service.delete_action(action_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete action: {str(e)}")
    return {"message": "Action deleted successfully"}
