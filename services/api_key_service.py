import hashlib
import os
import secrets

from database.sqlite import SqliteDatabase
from models.api_key import ApiKey


class ApiKeyService:
    def __init__(self, database: SqliteDatabase):
        self._db = database
        salt = os.getenv('API_KEY_SALT')
        if not salt:
            raise RuntimeError(
                'API_KEY_SALT must be set in .env — '
                'generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        self._salt = salt

    def _hash(self, raw_key: str) -> str:
        data = (self._salt + raw_key).encode('utf-8')
        return hashlib.sha256(data).hexdigest()

    def create_key(self, label: str) -> str:
        raw_key = secrets.token_urlsafe(32)
        key = ApiKey(key_hash=self._hash(raw_key), label=label)
        self._db.create_api_key(key)
        return raw_key

    def validate(self, raw_key: str) -> bool:
        if not raw_key:
            return False
        h = self._hash(raw_key)
        return self._db.get_api_key_by_hash(h) is not None

    def has_any_key(self) -> bool:
        return bool(self._db.get_all_api_keys())
