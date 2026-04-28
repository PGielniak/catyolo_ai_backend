from dataclasses import dataclass
from uuid import UUID, uuid4
from database.sqlite import SqliteDatabase
from models.action import Action

class ActionService:
    def __init__(self, database: SqliteDatabase):
        self.database = database
    def create_action(self, action_name: str,
                     action_type: str,
                     action_config: dict,):
        action = Action(action_name=action_name,
                     action_type=action_type,
                     action_config=action_config)

        self.database.create_action(action)
        return action

    def get_action(self, action_id: UUID):
        return self.database.get_action(action_id)

    def get_all_actions(self):
        return self.database.get_all_actions()

    def update_action(self, action_id: UUID,
                     action_name: str,
                     action_type: str,
                     action_config: dict):
        action = self.database.get_action(action_id)
        action.action_name = action_name
        action.action_type = action_type
        action.action_config = action_config
        if action_config is None:
            action.action_config = {}

        self.database.update_action(action)

        return action

    def delete_action(self, action_id: UUID):
        try:
            self.database.get_action(action_id)
        except Exception as e:
            raise e
        self.database.delete_action(action_id)
        return True
