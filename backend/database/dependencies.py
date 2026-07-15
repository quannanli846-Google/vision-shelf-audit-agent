"""FastAPI dependency providers for the repository and storage layers.

Chooses the Supabase-backed implementation when credentials are configured,
otherwise transparently falls back to the in-memory / local-filesystem
implementations so the whole app is runnable with zero cloud setup. Swapping
to real Supabase later is purely an env var change - no code changes.
"""
from functools import lru_cache
from pathlib import Path

from config import get_settings
from database.repository import AuditRepository, InMemoryAuditRepository, SupabaseAuditRepository
from database.storage import LocalMediaStorage, MediaStorage, SupabaseMediaStorage

BACKEND_DIR = Path(__file__).resolve().parent.parent


@lru_cache
def get_repository() -> AuditRepository:
    settings = get_settings()
    if settings.supabase_configured:
        from database.supabase_client import get_supabase_client

        return SupabaseAuditRepository(get_supabase_client())
    return InMemoryAuditRepository()


@lru_cache
def get_storage() -> MediaStorage:
    settings = get_settings()
    if settings.supabase_configured:
        from database.supabase_client import get_supabase_client

        return SupabaseMediaStorage(get_supabase_client(), settings.supabase_storage_bucket)
    return LocalMediaStorage(BACKEND_DIR / "sample_data" / "uploads")


def reset_dependency_caches() -> None:
    """Used by tests to force fresh instances between test cases."""
    get_repository.cache_clear()
    get_storage.cache_clear()
