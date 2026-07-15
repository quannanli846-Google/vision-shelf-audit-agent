"""Centralized application configuration, loaded from environment variables.

Every setting has a safe local-dev default so the application can boot and
be exercised end-to-end (in mock mode) without any external credentials.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Supabase ---
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_storage_bucket: str = "shelf-media"

    # --- Vision provider ---
    # "mock" runs the whole pipeline with a deterministic, clearly-labeled stub
    # vision client so no API key is required. "auto" prefers OpenAI (strict
    # json_schema enforcement) if OPENAI_API_KEY is set, then Groq (fast,
    # OpenAI-compatible, json_object mode only) if GROQ_API_KEY is set,
    # otherwise falls back to the mock. Any mode can also be forced explicitly.
    vision_provider: Literal["mock", "openai", "groq", "auto"] = "auto"
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o"
    groq_api_key: str = ""
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # --- Video pipeline tuning ---
    video_sample_fps: float = 1.0
    video_max_sampled_frames: int = 40
    video_max_frames_for_vision: int = 5
    video_blur_variance_threshold: float = 60.0
    video_duplicate_hash_threshold: int = 6  # hamming distance for average-hash dedupe
    video_dark_brightness_threshold: float = 40.0  # mean pixel intensity (0-255) below this = "too dark"
    video_overexposed_brightness_threshold: float = 215.0  # mean pixel intensity above this = "overexposed (glare)"
    video_gallery_thumbnail_max: int = 12  # cap on thumbnails embedded in the trace for the Analyzed Media UI

    # --- SKU grounding thresholds ---
    sku_match_high_threshold: float = 88.0
    sku_match_low_threshold: float = 60.0
    sku_match_ambiguous_margin: float = 5.0

    # --- Confidence calibration ---
    confidence_high_threshold: float = 0.75
    confidence_medium_threshold: float = 0.4

    # --- Misc ---
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://[::1]:5173"
    max_upload_size_mb: int = 200

    def resolved_vision_provider(self) -> Literal["mock", "openai", "groq"]:
        if self.vision_provider == "auto":
            if self.openai_api_key:
                return "openai"
            if self.groq_api_key:
                return "groq"
            return "mock"
        return self.vision_provider  # type: ignore[return-value]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
