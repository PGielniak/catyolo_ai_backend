from sqlalchemy import Column, Integer, String, LargeBinary, JSON, Text
from models.base import Base
import uuid
from dataclasses import dataclass

class Scene(Base):
    __tablename__ = 'scenes'
    
    scene_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_name = Column(String(255), nullable=False)
    camera_ip_address = Column(String(255), nullable=False)
    camera_port = Column(Integer, nullable=False)
    camera_username = Column(String(255), nullable=True)
    camera_password = Column(String(255), nullable=True)
    image = Column(LargeBinary)
    red_zones = Column(JSON)
    action_ids = Column(JSON)
    vlm_prompt = Column(Text, nullable=True)


@dataclass(frozen=True)
class CameraFrame:
    image: bytes

@dataclass(frozen=True)
class RedZone:
    x: int
    y: int
    width: int
    height: int
    forbidden_classes: list[str]
