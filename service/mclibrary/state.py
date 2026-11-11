"""Persistent record of which volume ids have been delivered.

The state lives in a hidden JSON file inside LIBRARY_DIR. Writes are atomic:
the new content goes to a temporary file in the same directory, is flushed to
disk, and then replaces the old file with ``os.replace``. If the process dies
mid-write the old file is left untouched.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

STATE_FILENAME = ".mclibrary_state.json"
STATE_VERSION = 1


class StateError(Exception):
    """The state file exists but cannot be read or written."""


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    @classmethod
    def in_library(cls, library_dir: Path) -> "StateStore":
        return cls(library_dir / STATE_FILENAME)

    def _load(self) -> dict[str, str]:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise StateError(f"durum dosyası okunamadı: {self.path} ({exc})") from exc
        try:
            data = json.loads(raw)
            delivered = data["delivered"]
            if not isinstance(delivered, dict):
                raise TypeError("'delivered' is not an object")
        except (ValueError, KeyError, TypeError) as exc:
            # Never silently reset: that would hand out every book again.
            raise StateError(f"durum dosyası bozuk: {self.path} ({exc})") from exc
        return {str(k): str(v) for k, v in delivered.items()}

    def _write(self, delivered: dict[str, str]) -> None:
        payload = json.dumps(
            {"version": STATE_VERSION, "delivered": delivered},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except BaseException as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            if isinstance(exc, OSError):
                raise StateError(f"durum dosyası yazılamadı: {self.path} ({exc})") from exc
            raise

    def delivered_ids(self) -> set[str]:
        with self._lock:
            return set(self._load())

    def mark_delivered(self, ids: list[str]) -> int:
        """Record ``ids`` as delivered. Returns how many were new."""
        with self._lock:
            delivered = self._load()
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            new = [i for i in dict.fromkeys(ids) if i not in delivered]
            if not new:
                return 0
            for volume_id in new:
                delivered[volume_id] = now
            self._write(delivered)
            return len(new)
