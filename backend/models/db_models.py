"""Pydantic models mirroring database rows (accounts, products, audits).

Kept separate from `shelf_audit.py` (the analysis-result schema) so the two
concerns - "what a row in the DB looks like" vs "what the AI pipeline
produces" - don't get tangled together.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Account(BaseModel):
    id: UUID
    store_name: str
    created_at: datetime


class Product(BaseModel):
    id: UUID
    brand: str
    product_name: str
    size: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


AuditStatus = Literal["uploaded", "processing", "completed", "failed"]


class Audit(BaseModel):
    id: UUID
    account_id: UUID
    media_url: str
    media_type: Literal["image", "video"]
    status: AuditStatus
    status_message: Optional[str] = None
    audit_json: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AuditCreateResponse(BaseModel):
    id: UUID
    status: AuditStatus


class AuditListItem(BaseModel):
    """Enriched summary row for the History page - includes the store name
    and overall confidence (when available) so the frontend doesn't need to
    separately fetch every account and every full audit_json just to render
    a table.
    """

    id: UUID
    account_id: UUID
    store_name: str
    media_type: Literal["image", "video"]
    status: AuditStatus
    overall_confidence: Optional[float] = None
    created_at: datetime


ReviewAction = Literal["confirm", "correct", "reject"]


class AuditFeedback(BaseModel):
    """A human reviewer's disposition on one AI-extracted field, persisted as
    an append-only log for future evaluation/calibration - this NEVER
    mutates the original `audits.audit_json`, which stays exactly what the
    pipeline produced at completion time.
    """

    id: UUID
    audit_id: UUID
    field: str = Field(description="Path identifying the reviewed field, e.g. \"products_observed[2].brand\"")
    review_action: ReviewAction
    ai_value: Optional[str] = Field(default=None, description="The value the AI originally extracted (as text), for context")
    ai_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    corrected_value: Optional[str] = Field(default=None, description="Only present when review_action == 'correct'")
    created_at: datetime


class AuditFeedbackCreate(BaseModel):
    field: str
    review_action: ReviewAction
    ai_value: Optional[str] = None
    ai_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    corrected_value: Optional[str] = None
