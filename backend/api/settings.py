"""Developer/demo-only settings endpoints.

`vision-provider` is NOT a field-representative feature - it's a control
panel toggle for switching the active `VisionClient` (Mock <-> OpenAI/Groq)
live, without restarting the backend, so a demo can show the pipeline is
genuinely provider-agnostic. Production deployments should configure
`VISION_PROVIDER` via environment variables instead (see
`config.py::Settings.resolved_vision_provider`) and would typically not
expose this router at all.

The route handlers below only ever read/write `VisionProviderState` - they
never construct a `VisionClient` themselves. Provider creation still happens
exactly once, in `services/audit_pipeline.py` via `vision/client.py`'s
factory - this module's whole job is picking *which* provider name that
factory will be called with for the next audit.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from config import Settings, get_settings
from models.vision_settings import ProviderName, VisionProviderOption, VisionProviderSelection, VisionProviderStatus
from services.vision_provider_state import VisionProviderState, get_vision_provider_state
from vision.client import VISION_PROVIDER_METADATA

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _availability(provider: ProviderName, settings: Settings) -> tuple[bool, Optional[str]]:
    if provider == "openai":
        return (True, None) if settings.openai_api_key else (False, "OPENAI_API_KEY is not configured on the backend")
    if provider == "groq":
        return (True, None) if settings.groq_api_key else (False, "GROQ_API_KEY is not configured on the backend")
    return True, None  # mock never needs a key


def _build_status(state: VisionProviderState, settings: Settings) -> VisionProviderStatus:
    active = state.active_provider
    meta = VISION_PROVIDER_METADATA[active]
    options = []
    for provider, provider_meta in VISION_PROVIDER_METADATA.items():
        available, reason = _availability(provider, settings)  # type: ignore[arg-type]
        options.append(
            VisionProviderOption(
                provider=provider,  # type: ignore[arg-type]
                label=provider_meta["label"],
                mode_label=provider_meta["mode_label"],
                description=provider_meta["description"],
                available=available,
                unavailable_reason=reason,
            )
        )
    return VisionProviderStatus(
        active_provider=active,
        label=meta["label"],
        mode_label=meta["mode_label"],
        description=meta["description"],
        is_dev_override=state.is_dev_override,
        default_provider=state.default_provider,
        options=options,
    )


@router.get("/vision-provider", response_model=VisionProviderStatus)
def get_vision_provider(
    state: VisionProviderState = Depends(get_vision_provider_state),
    settings: Settings = Depends(get_settings),
) -> VisionProviderStatus:
    return _build_status(state, settings)


@router.post("/vision-provider", response_model=VisionProviderStatus)
def set_vision_provider(
    payload: VisionProviderSelection,
    state: VisionProviderState = Depends(get_vision_provider_state),
    settings: Settings = Depends(get_settings),
) -> VisionProviderStatus:
    """Switch the active provider for every subsequent audit this process
    handles. Never touches an in-flight audit, and never persists past a
    backend restart - see the module docstring in
    `services/vision_provider_state.py` for why that's deliberate.
    """
    available, reason = _availability(payload.provider, settings)
    if not available:
        raise HTTPException(status_code=400, detail=f"Cannot switch to '{payload.provider}': {reason}")

    state.set_override(payload.provider)
    return _build_status(state, settings)
