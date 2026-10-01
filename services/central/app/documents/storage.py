"""Protected file storage behind a small interface (replaceable by object storage).

Files are stored under generated names outside any web root and are only
served through authenticated endpoints.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from ..config import settings


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        if "/" in key or "\\" in key or ".." in key:
            raise ValueError("invalid storage key")
        return self.root / key

    def put(self, data: bytes, suffix: str = ".bin") -> tuple[str, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        key = f"{uuid.uuid4().hex}{suffix}"
        self._path(key).write_bytes(data)
        return key, hashlib.sha256(data).hexdigest()

    def put_named(self, key: str, data: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(key).write_bytes(data)

    def path(self, key: str) -> Path:
        return self._path(key)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


storage = LocalStorage(settings.storage_root)
