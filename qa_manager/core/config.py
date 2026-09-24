from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    artifact_dir: Path
    database_path: Path
    host: str = "127.0.0.1"
    port: int = 8787
    max_concurrent_runs: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(os.getenv("QAROZ_HOME", Path.cwd())).resolve()
        data = Path(os.getenv("QAROZ_DATA_DIR", base / "data")).resolve()
        artifacts = Path(os.getenv("QAROZ_ARTIFACT_DIR", base / "artifacts")).resolve()
        return cls(
            base_dir=base,
            data_dir=data,
            artifact_dir=artifacts,
            database_path=Path(
                os.getenv("QAROZ_DATABASE", data / "qaroz.db")
            ).resolve(),
            host=os.getenv("QAROZ_HOST", "127.0.0.1"),
            port=int(os.getenv("QAROZ_PORT", "8787")),
            max_concurrent_runs=max(
                1, int(os.getenv("QAROZ_MAX_CONCURRENT_RUNS", "3"))
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
