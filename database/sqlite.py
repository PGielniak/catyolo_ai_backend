from sqlalchemy import create_engine, MetaData, Table, Column, inspect
from sqlalchemy.orm import sessionmaker, Session
import sqlite3
from uuid import UUID
from models.scene import Scene, Base
from models.action import Action
from contextlib import contextmanager

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
        """Add columns introduced after initial schema creation."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(scenes)")
            cols = {row[1] for row in cur.fetchall()}
            if 'camera_username' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN camera_username TEXT")
            if 'camera_password' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN camera_password TEXT")
            if 'vlm_prompt' not in cols:
                conn.execute("ALTER TABLE scenes ADD COLUMN vlm_prompt TEXT")
            conn.commit()

    def create_tables(self):
        Base.metadata.create_all(self.engine)

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

    def close(self):
        self.engine.dispose()

