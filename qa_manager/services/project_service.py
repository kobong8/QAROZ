from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from qa_manager.core.database import Database, utcnow
from qa_manager.core.security import validate_http_url


class ProjectService:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict[str, Any]]:
        return self.db.fetchall("SELECT * FROM projects ORDER BY created_at")

    def get(self, project_id: str) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = dict(payload)
        name = str(value.get("name", "")).strip()
        if not name:
            raise ValueError("Project name is required")
        value["name"] = name
        value["frontend_url"] = validate_http_url(
            str(value.get("frontend_url", ""))
        ).rstrip("/")
        for key in ("backend_url", "health_url"):
            if value.get(key):
                value[key] = validate_http_url(str(value[key])).rstrip("/")
        if value.get("project_path"):
            path = Path(value["project_path"]).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise ValueError("Project path must be an existing directory")
            value["project_path"] = str(path)
        ports = value.get("expected_ports", [])
        if isinstance(ports, str):
            ports = [int(item.strip()) for item in ports.split(",") if item.strip()]
        if any(not isinstance(port, int) or not 1 <= port <= 65535 for port in ports):
            raise ValueError("Expected ports must be between 1 and 65535")
        value["expected_ports"] = sorted(set(ports))
        rules = value.get("process_rules", [])
        value["process_rules"] = (
            [str(rule).strip() for rule in rules if str(rule).strip()]
            if isinstance(rules, list)
            else [r.strip() for r in rules.split(",") if r.strip()]
        )
        value["enabled"] = bool(value.get("enabled", True))
        return value

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = self.validate(payload)
        value.update(id=str(uuid.uuid4()), created_at=utcnow())
        self.db.insert("projects", value)
        return self.get(value["id"])  # type: ignore[return-value]

    def update(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.get(project_id):
            return None
        current = self.get(project_id) or {}
        allowed = {
            "name",
            "frontend_url",
            "backend_url",
            "project_path",
            "health_url",
            "expected_ports",
            "process_rules",
            "enabled",
        }
        value = self.validate(
            {**current, **{k: v for k, v in payload.items() if k in allowed}}
        )
        encoded = dict(value)
        for key in ("expected_ports", "process_rules"):
            encoded[key] = json.dumps(encoded[key])
        assignments = ",".join(f"{key}=?" for key in encoded)
        self.db.execute(
            f"UPDATE projects SET {assignments} WHERE id=?",
            (*encoded.values(), project_id),
        )
        return self.get(project_id)

    def delete(self, project_id: str) -> bool:
        if not self.get(project_id):
            return False
        self.db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return True
