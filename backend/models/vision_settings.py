"""Schemas for the developer/demo "Vision Provider" switch
(`api/settings.py`).

Not part of the trusted ShelfAudit domain - this is operational/developer
tooling metadata, kept in its own module so it's obvious at a glance that
none of it flows into audit data.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ProviderName = Literal["mock", "openai", "groq"]


class VisionProviderOption(BaseModel):
    provider: ProviderName
    label: str
    mode_label: str
    description: str
    available: bool = Field(description="False when the API key this provider needs isn't configured on the backend")
    unavailable_reason: Optional[str] = None


class VisionProviderStatus(BaseModel):
    active_provider: ProviderName
    label: str
    mode_label: str
    description: str
    is_dev_override: bool = Field(description="True once a developer has explicitly switched providers this process run")
    default_provider: ProviderName = Field(description="What VISION_PROVIDER (env var) resolves to - restored on backend restart")
    options: list[VisionProviderOption]


class VisionProviderSelection(BaseModel):
    provider: ProviderName
