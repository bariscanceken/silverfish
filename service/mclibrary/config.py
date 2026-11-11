"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_AUTHOR = "Silverfish"


@dataclass(frozen=True)
class Settings:
    library_dir: Path
    author: str

    @classmethod
    def from_env(cls) -> "Settings":
        raw_dir = os.environ.get("LIBRARY_DIR")
        if not raw_dir:
            raise RuntimeError("LIBRARY_DIR environment variable is not set")
        author = os.environ.get("LIBRARY_AUTHOR", "").strip() or DEFAULT_AUTHOR
        return cls(library_dir=Path(raw_dir), author=author)
