from uuid import UUID
from database.sqlite import SqliteDatabase
from models.action import Action

# Must match the suffixes used in routes/action.py for consistent semantics
_SENSITIVE_SUFFIXES = ("Token", "Password", "Secret", "ApiKey")


def _is_sensitive(key: str) -> bool:
    return any(key.endswith(s) for s in _SENSITIVE_SUFFIXES)


class ActionService:
    def __init__(self, database: SqliteDatabase):
        self.database = database

    def create_action(self, action_name: str, action_type: str, action_config: dict):
        action = Action(
            action_name=action_name,
            action_type=action_type,
            action_config=action_config,
        )
        self.database.create_action(action)
        return action

    def get_action(self, action_id: UUID):
        return self.database.get_action(action_id)

    def get_all_actions(self):
        return self.database.get_all_actions()

    def update_action(self, action_id: UUID, action_name: str, action_type: str, action_config: dict):
        action = self.database.get_action(action_id)
        action.action_name = action_name
        action.action_type = action_type
        # Write-only: if an incoming sensitive value is "", keep the stored one
        existing = action.action_config or {}
        merged = dict(action_config) if action_config else {}
        for k, v in merged.items():
            if v == "" and _is_sensitive(k) and k in existing and existing[k]:
                merged[k] = existing[k]
        action.action_config = merged
        self.database.update_action(action)
        return action

    def delete_action(self, action_id: UUID):
        try:
            self.database.get_action(action_id)
        except Exception as e:
            raise e
        self.database.delete_action(action_id)
        return True
