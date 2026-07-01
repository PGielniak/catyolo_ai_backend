from sqlalchemy import create_engine, MetaData, Table, Column, inspect
from sqlalchemy.orm import sessionmaker, Session
import sqlite3
import json
import logging
from uuid import UUID
from models.scene import Scene, Base
from models.action import Action
from models.api_key import ApiKey
from contextlib import contextmanager

logger = logging.getLogger("catyolo_backend")

class SqliteDatabase:
    def __init__(self, db_path: str = "catyolo.db"):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def get_session(self) -> Session:
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def migrate(self):
        """Add columns introduced after initial schema creation and drop removed ones."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(scenes)")
            cols = {row[1] for row in cur.fetchall()}
            if 'camera_username' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN camera_username TEXT")
            if 'camera_password' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN camera_password TEXT")
            if 'scene_prompt' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN scene_prompt TEXT")
            if 'scene_prompt_interval' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN scene_prompt_interval INTEGER")
            if 'scene_prompt_action_ids' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN scene_prompt_action_ids JSON")
            if 'global_detection_enabled' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN global_detection_enabled INTEGER NOT NULL DEFAULT 0")
            if 'global_detection_classes' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN global_detection_classes JSON")
            if 'global_detection_action_ids' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN global_detection_action_ids JSON")
            if 'global_detection_cooldown_seconds' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN global_detection_cooldown_seconds INTEGER NOT NULL DEFAULT 60")
            if 'version' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
            if 'action_ids' in cols:
                try:
                    conn.execute("ALTER TABLE scenes DROP COLUMN action_ids")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not drop scenes.action_ids column: {e}")
            if 'vlm_prompt' in cols:
                self._backfill_vlm_prompt_into_red_zones(conn)
                try:
                    conn.execute("ALTER TABLE scenes DROP COLUMN vlm_prompt")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not drop scenes.vlm_prompt column: {e}")
            conn.commit()

    @staticmethod
    def _backfill_vlm_prompt_into_red_zones(conn: sqlite3.Connection):
        cur = conn.cursor()
        cur.execute(
            "SELECT scene_id, red_zones, vlm_prompt FROM scenes "
            "WHERE vlm_prompt IS NOT NULL AND vlm_prompt != ''"
        )
        for scene_id, red_zones_raw, vlm_prompt in cur.fetchall():
            try:
                red_zones = json.loads(red_zones_raw) if red_zones_raw else []
            except (TypeError, json.JSONDecodeError):
                logger.warning(f"Skipping vlm_prompt backfill for scene {scene_id}: invalid red_zones JSON")
                continue
            if not isinstance(red_zones, list):
                continue
            changed = False
            for rz in red_zones:
                if isinstance(rz, dict) and not rz.get('vlm_prompt'):
                    rz['vlm_prompt'] = vlm_prompt
                    changed = True
            if changed:
                conn.execute(
                    "UPDATE scenes SET red_zones = ? WHERE scene_id = ?",
                    (json.dumps(red_zones), scene_id),
                )
                logger.info(f"Backfilled scene-level vlm_prompt into red zones for scene {scene_id}")

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    # ── Scene ──────────────────────────────────────────────────────────

    def create_scene(self, scene: Scene):
        with self.get_session() as session:
            session.add(scene)

    def get_scene(self, scene_id: UUID):
        with self.get_session() as session:
            return session.query(Scene).get(str(scene_id))

    def update_scene(self, scene: Scene):
        with self.get_session() as session:
            session.merge(scene)

    def delete_scene(self, scene_id: UUID):
        with self.get_session() as session:
            session.query(Scene).filter(Scene.scene_id == str(scene_id)).delete()

    def get_all_scenes(self):
        with self.get_session() as session:
            return session.query(Scene).all()

    # ── Action ─────────────────────────────────────────────────────────

    def create_action(self, action: Action):
        with self.get_session() as session:
            session.add(action)

    def get_action(self, action_id: UUID):
        with self.get_session() as session:
            return session.query(Action).get(str(action_id))

    def get_all_actions(self):
        with self.get_session() as session:
            return session.query(Action).all()

    def update_action(self, action: Action):
        with self.get_session() as session:
            session.merge(action)

    def delete_action(self, action_id: UUID):
        with self.get_session() as session:
            session.query(Action).filter(Action.action_id == str(action_id)).delete()

    # ── ApiKey ─────────────────────────────────────────────────────────

    def create_api_key(self, key: ApiKey):
        with self.get_session() as session:
            session.add(key)

    def get_api_key_by_hash(self, key_hash: str):
        with self.get_session() as session:
            return session.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

    def get_all_api_keys(self):
        with self.get_session() as session:
            return session.query(ApiKey).all()

    def close(self):
        self.engine.dispose()
