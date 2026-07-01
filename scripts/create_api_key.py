#!/usr/bin/env python3
"""Bootstrap: create an API key and store its hash in the database."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from database.sqlite import SqliteDatabase
from services.api_key_service import ApiKeyService


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else input("Key label (e.g. 'worker', 'frontend'): ").strip()
    if not label:
        print("Label cannot be empty.", file=sys.stderr)
        sys.exit(1)

    db_path = os.getenv("DATABASE_PATH", "catyolo.db")
    db = SqliteDatabase(db_path)
    db.create_tables()

    service = ApiKeyService(db)
    raw_key = service.create_key(label)
    db.close()

    print(f"\nAPI key created for label '{label}':")
    print(f"  {raw_key}")
    print("\nAdd to .env files:")
    print(f"  API_KEY={raw_key}")


if __name__ == "__main__":
    main()
