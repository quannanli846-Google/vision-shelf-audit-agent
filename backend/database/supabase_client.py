"""Thin factory for the official supabase-py client.

Isolated in its own module so nothing else in the codebase imports the
`supabase` package directly - if the SDK ever changes, this is the only
file that needs to change.
"""
from functools import lru_cache

from supabase import Client, create_client

from config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise RuntimeError(
            "Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY missing). "
            "Set them in backend/.env, or rely on the in-memory dev repository."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)
