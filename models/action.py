from sqlalchemy import Column, Integer, String, LargeBinary, JSON
import uuid
from models.base import Base

class Action(Base):
    __tablename__ = 'actions'

    action_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_name = Column(String(255), nullable=False)
    action_type = Column(String(255), nullable=False)
    action_config = Column(JSON, nullable=True)