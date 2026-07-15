"""FastAPI application entrypoint.

Route modules never talk to Supabase, OpenAI, or the filesystem directly -
they depend only on the repository/storage/pipeline abstractions wired up
here and in `database/dependencies.py`.
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import accounts, audits, products
from api import settings as settings_api
from config import Settings, get_settings
from services.vision_provider_state import VisionProviderState, get_vision_provider_state

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="Vision AI Shelf Audit API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(products.router)
app.include_router(audits.router)
app.include_router(settings_api.router)

# Serves locally-stored media when Supabase Storage isn't configured (dev/demo fallback).
_local_media_dir = Path(__file__).resolve().parent / "sample_data" / "uploads"
_local_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_local_media_dir)), name="media")


@app.get("/api/health")
def health(
    request_settings: Settings = Depends(get_settings),
    provider_state: VisionProviderState = Depends(get_vision_provider_state),
) -> dict:
    return {
        "status": "ok",
        # Reflects the developer "Vision Provider" switch (api/settings.py)
        # if one has been used this process run, otherwise the environment-
        # configured default - always the provider the *next* audit would
        # actually use, never a stale/static value.
        "vision_provider": provider_state.active_provider,
        "vision_provider_is_dev_override": provider_state.is_dev_override,
        "supabase_configured": request_settings.supabase_configured,
    }
