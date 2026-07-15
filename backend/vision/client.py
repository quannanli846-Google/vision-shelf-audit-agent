"""VisionClient abstraction: swap between vision providers purely via
configuration. Nothing outside this module (and `vision/providers/`) ever
imports a provider SDK directly - `vision/extractor.py` only ever depends on
the `VisionClient` interface below and calls `analyze_frame()` - which is
what lets the pipeline be unit-tested without network access or an API key,
and what lets a new provider be added without touching extractor/pipeline
code at all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class VisionClient(ABC):
    #: Human-readable identity shown in the AI Processing Trace (e.g. "OpenAI
    #: Vision", "Mock Vision"). Every concrete provider must set this - it's
    #: how the pipeline/UI reveal *which* replaceable perception backend
    #: produced a given audit, without the rest of the app ever branching on
    #: provider type.
    provider_name: str = "Unknown Vision Provider"

    @abstractmethod
    def analyze_frame(self, image_bytes: bytes, frame_id: str, frame_context: str = "") -> str:
        """Return the raw (untrusted) JSON text produced by the vision model for one frame.

        Implementations must return ONLY raw observations - never anything
        validated/grounded/calibrated. `vision/validator.py` is the only
        thing downstream allowed to turn this into trusted data.
        """


#: Static metadata for every known provider, independent of whether it can
#: actually be instantiated right now (that depends on API keys - see
#: `api/settings.py::_availability`). This is what powers the developer
#: "Vision Provider" switch in the frontend and the `/api/settings/vision-provider`
#: endpoint - it deliberately lives next to the factory it describes so the
#: two can never drift out of sync.
VISION_PROVIDER_METADATA: dict[str, dict[str, str]] = {
    "openai": {
        "label": "OpenAI Vision",
        "mode_label": "Real inference enabled",
        "description": "Calls a real OpenAI vision model (GPT-4o) for genuine image/video understanding.",
    },
    "groq": {
        "label": "Groq Vision",
        "mode_label": "Real inference enabled (Groq)",
        "description": "Calls a real Groq-hosted vision model (Llama-4-Scout) for genuine image/video understanding.",
    },
    "mock": {
        "label": "Mock Vision",
        "mode_label": "Deterministic testing mode",
        "description": "Deterministic fixture responses - no network calls, no API key required.",
    },
}


def build_vision_client(
    provider: str,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o",
    groq_api_key: str = "",
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> VisionClient:
    """Provider factory. Each branch lazily imports its provider module so
    an unused provider's SDK is never even imported, let alone required."""
    if provider == "openai":
        if not openai_api_key:
            raise ValueError("VISION_PROVIDER=openai but OPENAI_API_KEY is not set")
        from vision.providers.openai import OpenAIVisionClient

        return OpenAIVisionClient(api_key=openai_api_key, model=openai_model)

    if provider == "groq":
        if not groq_api_key:
            raise ValueError("VISION_PROVIDER=groq but GROQ_API_KEY is not set")
        from vision.providers.groq import GroqVisionClient

        return GroqVisionClient(api_key=groq_api_key, model=groq_model)

    from vision.providers.mock import MockVisionClient

    return MockVisionClient()
