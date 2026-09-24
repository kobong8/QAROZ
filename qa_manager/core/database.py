from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .security import protect_for_storage

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, frontend_url TEXT NOT NULL, backend_url TEXT,
 project_path TEXT, health_url TEXT, expected_ports TEXT NOT NULL DEFAULT '[]',
 process_rules TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 backend_urls TEXT NOT NULL DEFAULT '[]', health_urls TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS api_test_cases (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, method TEXT NOT NULL, url TEXT NOT NULL, headers TEXT NOT NULL DEFAULT '{}',
 query TEXT NOT NULL DEFAULT '{}', body TEXT, expected_status INTEGER NOT NULL DEFAULT 200,
 assertions TEXT NOT NULL DEFAULT '{}', max_response_ms INTEGER, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS scenarios (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, runner_ref TEXT, steps TEXT NOT NULL DEFAULT '[]', expected TEXT NOT NULL DEFAULT '[]',
 enabled INTEGER NOT NULL DEFAULT 1, tags TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS test_runs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 suite TEXT NOT NULL, trigger TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
 status TEXT NOT NULL, current_stage TEXT, duration_ms INTEGER
);
CREATE TABLE IF NOT EXISTS test_results (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
 category TEXT NOT NULL, test_name TEXT NOT NULL, status TEXT NOT NULL, duration_ms INTEGER NOT NULL,
 message TEXT, details TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, result_id TEXT NOT NULL REFERENCES test_results(id) ON DELETE CASCADE,
 type TEXT NOT NULL, local_path TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS zap_alerts (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
 risk TEXT, confidence TEXT, url TEXT, name TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_runs_project ON test_runs(project_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_results_run ON test_results(run_id);
"""

JSON_FIELDS = {
    "expected_ports",
    "process_rules",
    "backend_urls",
    "health_urls",
    "headers",
    "query",
    "body",
    "assertions",
    "steps",
    "expected",
    "tags",
    "details",
    "metadata",
}


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(projects)")
            }
            for column in ("backend_urls", "health_urls"):
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE projects ADD COLUMN {column} TEXT NOT NULL DEFAULT '[]'"
                    )
            # Preserve projects created by releases that only supported one backend.
            connection.execute(
                "UPDATE projects SET backend_urls=json_array(backend_url) "
                "WHERE backend_url IS NOT NULL AND backend_url != '' AND backend_urls='[]'"
            )
            connection.execute(
                "UPDATE projects SET health_urls=json_array(health_url) "
                "WHERE health_url IS NOT NULL AND health_url != '' AND health_urls='[]'"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for key in JSON_FIELDS & result.keys():
            if result[key] is not None:
                try:
                    result[key] = json.loads(result[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        if "enabled" in result:
            result["enabled"] = bool(result["enabled"])
        return result

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as connection:
            return self.decode(connection.execute(sql, params).fetchone())

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [self.decode(row) for row in connection.execute(sql, params).fetchall()]  # type: ignore[misc]

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(sql, params)

    def insert(self, table: str, data: dict[str, Any]) -> str:
        clean = protect_for_storage(data)
        identifier = str(clean.get("id") or uuid.uuid4())
        clean["id"] = identifier
        encoded = {
            k: (
                json.dumps(v, ensure_ascii=False)
                if k in JSON_FIELDS and v is not None
                else v
            )
            for k, v in clean.items()
        }
        columns = ",".join(encoded)
        placeholders = ",".join("?" for _ in encoded)
        self.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(encoded.values()),
        )
        return identifier
