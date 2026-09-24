from __future__ import annotations

from pathlib import Path


class ArtifactService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, project_id: str, run_id: str) -> Path:
        safe_project = "".join(c for c in project_id if c.isalnum() or c in "-_")
        safe_run = "".join(c for c in run_id if c.isalnum() or c in "-_")
        path = (self.root / safe_project / safe_run).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact path escapes configured root")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve(self, local_path: str) -> Path:
        path = Path(local_path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("Artifact is outside the configured root")
        return path
