"""Media storage abstraction: uploaded shelf images/videos.

Mirrors the repository pattern - route/pipeline code depends only on the
`MediaStorage` interface, never on Supabase Storage or the filesystem
directly, so storage is swappable and independently testable.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class MediaStorage(ABC):
    @abstractmethod
    def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Persist the file and return a URL/path the frontend can load it from."""

    @abstractmethod
    def read(self, media_reference: str) -> bytes:
        """Read back raw bytes for a previously-uploaded media reference (used by the vision pipeline)."""


class SupabaseMediaStorage(MediaStorage):
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def _storage_path(self, filename: str) -> str:
        ext = Path(filename).suffix
        return f"{uuid.uuid4()}{ext}"

    def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        path = self._storage_path(filename)
        self._client.storage.from_(self._bucket).upload(
            path, file_bytes, file_options={"content-type": content_type}
        )
        return self._client.storage.from_(self._bucket).get_public_url(path)

    def read(self, media_reference: str) -> bytes:
        # media_reference is the public URL; extract the storage path (last path segment(s) after the bucket name).
        marker = f"/{self._bucket}/"
        idx = media_reference.find(marker)
        path = media_reference[idx + len(marker):] if idx != -1 else media_reference
        return self._client.storage.from_(self._bucket).download(path)


class LocalMediaStorage(MediaStorage):
    """Filesystem-backed fallback so the app is fully runnable before a
    Supabase project/Storage bucket exists. Files are written under
    `backend/sample_data/uploads/` and served by FastAPI via a mounted
    static route (see `main.py`).
    """

    def __init__(self, base_dir: Path, public_prefix: str = "/media"):
        self._base_dir = base_dir
        self._public_prefix = public_prefix
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        ext = Path(filename).suffix
        stored_name = f"{uuid.uuid4()}{ext}"
        (self._base_dir / stored_name).write_bytes(file_bytes)
        return f"{self._public_prefix}/{stored_name}"

    def read(self, media_reference: str) -> bytes:
        stored_name = media_reference.rsplit("/", 1)[-1]
        return (self._base_dir / stored_name).read_bytes()
