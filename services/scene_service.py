from dataclasses import dataclass, asdict
from uuid import UUID, uuid4
from database.sqlite import SqliteDatabase
from models.scene import Scene, RedZone


class SceneService:
    def _red_zones_to_dict(self, red_zones: list[RedZone]) -> list[dict]:
        if not red_zones:
            return []
        return [asdict(zone) for zone in red_zones]

    def _red_zones_from_dict(self, red_zones_data: list[dict]) -> list[RedZone]:
        if not red_zones_data:
            return []
        return [RedZone(**zone_dict) for zone_dict in red_zones_data]

    def __init__(self, database: SqliteDatabase):
        self.database = database

    def create_scene(self, scene_name: str,
                     camera_ip_address: str,
                     camera_port: int,
                     image: bytes,
                     red_zones: list[RedZone],
                     camera_username: str = None,
                     camera_password: str = None,
                     scene_prompt: str = None,
                     scene_prompt_interval: int = None,
                     scene_prompt_action_ids: list[UUID] = None,
                     global_detection_enabled: bool = False,
                     global_detection_classes: list[str] = None,
                     global_detection_action_ids: list[UUID] = None,
                     global_detection_cooldown_seconds: int = 60):
        scene_prompt_action_ids_str = [str(uuid) for uuid in scene_prompt_action_ids] if scene_prompt_action_ids else scene_prompt_action_ids
        global_detection_action_ids_str = [str(uuid) for uuid in global_detection_action_ids] if global_detection_action_ids else global_detection_action_ids
        red_zones_dict = self._red_zones_to_dict(red_zones)
        scene = Scene(
            scene_name=scene_name,
            camera_ip_address=camera_ip_address,
            camera_port=camera_port,
            camera_username=camera_username,
            camera_password=camera_password,
            image=image,
            red_zones=red_zones_dict,
            scene_prompt=scene_prompt,
            scene_prompt_interval=scene_prompt_interval,
            scene_prompt_action_ids=scene_prompt_action_ids_str,
            global_detection_enabled=1 if global_detection_enabled else 0,
            global_detection_classes=global_detection_classes or [],
            global_detection_action_ids=global_detection_action_ids_str,
            global_detection_cooldown_seconds=global_detection_cooldown_seconds or 60,
            version=1,
        )
        self.database.create_scene(scene)
        return scene

    def get_scene(self, scene_id: UUID):
        return self.database.get_scene(scene_id)

    def get_all_scenes(self):
        return self.database.get_all_scenes()

    def update_scene(self, scene_id: UUID,
                     scene_name: str,
                     camera_ip_address: str,
                     camera_port: int,
                     image: bytes,
                     red_zones: list[RedZone],
                     camera_username: str = None,
                     camera_password: str = None,
                     scene_prompt: str = None,
                     scene_prompt_interval: int = None,
                     scene_prompt_action_ids: list[UUID] = None,
                     global_detection_enabled: bool = False,
                     global_detection_classes: list[str] = None,
                     global_detection_action_ids: list[UUID] = None,
                     global_detection_cooldown_seconds: int = 60):
        scene = self.database.get_scene(scene_id)
        scene.scene_name = scene_name
        scene.camera_ip_address = camera_ip_address
        scene.camera_port = camera_port
        scene.camera_username = camera_username
        # Write-only: empty string from UI means "unchanged" — keep stored value
        if camera_password:
            scene.camera_password = camera_password
        scene.image = image
        scene.red_zones = self._red_zones_to_dict(red_zones)
        scene.scene_prompt = scene_prompt
        scene.scene_prompt_interval = scene_prompt_interval
        if scene_prompt_action_ids:
            scene.scene_prompt_action_ids = [str(uuid) for uuid in scene_prompt_action_ids]
        else:
            scene.scene_prompt_action_ids = scene_prompt_action_ids
        scene.global_detection_enabled = 1 if global_detection_enabled else 0
        scene.global_detection_classes = global_detection_classes or []
        if global_detection_action_ids:
            scene.global_detection_action_ids = [str(uuid) for uuid in global_detection_action_ids]
        else:
            scene.global_detection_action_ids = global_detection_action_ids
        scene.global_detection_cooldown_seconds = global_detection_cooldown_seconds or 60
        scene.version = (scene.version or 0) + 1
        self.database.update_scene(scene)
        return scene

    def delete_scene(self, scene_id: UUID):
        try:
            self.database.get_scene(scene_id)
        except Exception as e:
            raise e
        self.database.delete_scene(scene_id)
        return True

    def analyze_scene(self, scene_id: UUID) -> str:
        return "In the room there is one cat"
