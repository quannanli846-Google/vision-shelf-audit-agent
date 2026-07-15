"""Process-wide runtime override for which vision provider is active.

This exists ONLY to back the developer/demo "Vision Provider" switch exposed
by the frontend (see `api/settings.py`) - it is explicitly NOT a field-
representative feature, not a per-account setting, and not persisted to a
database. It lets someone flip between Mock Vision and a real provider live,
without restarting the backend, to demonstrate that the pipeline genuinely
doesn't care which `VisionClient` implementation is behind it.

A real production deployment would never need this module at all - the
provider would be fixed for the life of the process via the `VISION_PROVIDER`
environment variable (`config.py::Settings.resolved_vision_provider`). This
override simply takes priority over that env-derived default *while the
process is running*, and is lost on restart - by design, since a restart
should always fall back to the operator-configured, deployment-safe default.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

ProviderName = Literal["mock", "openai", "groq"]


class VisionProviderState:
    """Tiny in-memory state holder, one instance per running backend process.

    Not thread/coroutine-safe beyond what Python's GIL already gives simple
    attribute reads/writes - acceptable here because this is a single-writer
    developer control, not a concurrent multi-tenant setting.
    """

    def __init__(self, default_provider: ProviderName):
        self._default = default_provider
        self._override: Optional[ProviderName] = None

    @property
    def default_provider(self) -> ProviderName:
        """The env-derived provider that's active until/unless overridden -
        what a fresh restart of the process would go back to."""
        return self._default

    @property
    def active_provider(self) -> ProviderName:
        """Whichever provider `services/audit_pipeline.py` should actually
        use for the *next* audit: the dev override if one is set, otherwise
        the environment-configured default."""
        return self._override if self._override is not None else self._default

    @property
    def is_dev_override(self) -> bool:
        return self._override is not None

    def set_override(self, provider: ProviderName) -> None:
        self._override = provider

    def clear_override(self) -> None:
        """Not exposed over the API today, but kept so a future 'reset to
        environment default' control has somewhere to call into."""
        self._override = None


@lru_cache
def get_vision_provider_state() -> VisionProviderState:
    from config import get_settings

    return VisionProviderState(default_provider=get_settings().resolved_vision_provider())
