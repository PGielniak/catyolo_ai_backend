from sqlalchemy import Column, String
from models.base import Base
from datetime import datetime, timezone
import uuid


class ApiKey(Base):
    __tablename__ = 'api_keys'

    key_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(64), unique=True, nullable=False)
    label = Column(String(255), nullable=False)
    created_at = Column(String(19), nullable=False,
                        default=lambda: datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
