"""
Durable key -> JSON storage for user accounts and their workspaces.

Two backends with the same tiny interface (``read(key)`` / ``write(key, data)``):

* FileStorage      one JSON file per key under KAIROS_DATA_DIR (default
                   ``kairos_data``). Good for running KAIROS on your own computer.
* PostgresStorage  one row per key in a ``kairos_kv`` table. Used when
                   KAIROS_DATABASE_URL is set, because free hosts such as Render
                   wipe the server's disk whenever the service restarts.
"""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Optional, Protocol


class Storage(Protocol):
    def read(self, key: str) -> Optional[Any]: ...
    def write(self, key: str, data: Any) -> None: ...
    def describe(self) -> str: ...


_SAFE_KEY = re.compile(r"[^a-z0-9_.-]")


class FileStorage:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self._lock = threading.Lock()

    def _path(self, key: str) -> str:
        # keys are internal ("accounts", "workspace:alice"); keep file names tame
        return os.path.join(self.base_dir, _SAFE_KEY.sub("_", key.lower()) + ".json")

    def read(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, key: str, data: Any) -> None:
        path = self._path(key)
        with self._lock:
            os.makedirs(self.base_dir, exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)

    def describe(self) -> str:
        return f"files in {os.path.abspath(self.base_dir)}"


class PostgresStorage:
    def __init__(self, url: str) -> None:
        import psycopg  # only needed when a database is configured

        self._psycopg = psycopg
        self.url = url
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kairos_kv ("
                " key TEXT PRIMARY KEY, value JSONB NOT NULL,"
                " updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )

    def _connect(self):
        return self._psycopg.connect(self.url, autocommit=True)

    def read(self, key: str) -> Optional[Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM kairos_kv WHERE key = %s", (key,)).fetchone()
        return row[0] if row else None

    def write(self, key: str, data: Any) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO kairos_kv (key, value) VALUES (%s, %s)"
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (key, self._psycopg.types.json.Jsonb(data)),
            )

    def describe(self) -> str:
        return "the KAIROS database"


def from_environment() -> Storage:
    url = os.environ.get("KAIROS_DATABASE_URL", "").strip()
    if url:
        return PostgresStorage(url)
    return FileStorage(os.environ.get("KAIROS_DATA_DIR", "kairos_data"))
