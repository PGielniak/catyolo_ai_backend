from dataclasses import dataclass, asdict
from uuid import UUID, uuid4
from database.sqlite import SqliteDatabase
from models.scene import Scene, RedZone

class SceneService:
    def _red_zones_to_dict(self, red_zones: list[RedZone]) -> list[dict]:
        """Convert RedZone objects to dictionaries for JSON serialization"""
        if not red_zones:
            return []
        return [asdict(zone) for zone in red_zones]
    
    def _red_zones_from_dict(self, red_zones_data: list[dict]) -> list[RedZone]:
        """Convert dictionaries back to RedZone objects"""
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
                     action_ids: list[UUID] = None,
                     camera_username: str = None,
                     camera_password: str = None,
                     vlm_prompt: str = None):
        # Convert UUID objects to strings for JSON serialization
        action_ids_str = [str(uuid) for uuid in action_ids] if action_ids else action_ids
        # Convert RedZone objects to dicts for JSON serialization
        red_zones_dict = self._red_zones_to_dict(red_zones)
        scene = Scene(scene_name=scene_name,
                     camera_ip_address=camera_ip_address,
                     camera_port=camera_port,
                     camera_username=camera_username,
                     camera_password=camera_password,
                     image=image,
                     red_zones=red_zones_dict,
                     action_ids=action_ids_str,
                     vlm_prompt=vlm_prompt)
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
                     action_ids: list[UUID] = None,
                     camera_username: str = None,
                     camera_password: str = None,
                     vlm_prompt: str = None):
        scene = self.database.get_scene(scene_id)
        scene.scene_name = scene_name
        scene.camera_ip_address = camera_ip_address
        scene.camera_port = camera_port
        scene.camera_username = camera_username
        scene.camera_password = camera_password
        scene.image = image
        # Convert RedZone objects to dicts for JSON serialization
        scene.red_zones = self._red_zones_to_dict(red_zones)
        # Convert UUID objects to strings for JSON serialization
        if action_ids:
            scene.action_ids = [str(uuid) for uuid in action_ids]
        else:
            scene.action_ids = action_ids
        scene.vlm_prompt = vlm_prompt
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
