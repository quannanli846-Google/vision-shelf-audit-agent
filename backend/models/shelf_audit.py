"""The ShelfAudit schema: the ONLY shape of data that is ever persisted to
`audits.audit_json`.

Design principle (anti-hallucination): confidence is FIELD-LEVEL, not just
audit-level or item-level. Every individually extracted attribute is wrapped
in `ExtractedField[T]`, carrying its own value/confidence/reason. A field that
cannot be confidently determined must be returned as
`{"value": null, "confidence": <low>, "reason": "<why>"}` rather than guessed.

This module contains only validated, trusted, grounded data structures.
Raw/untrusted model output lives in `models/raw_observation.py` and must pass
through `vision/validator.py` before it can be assembled into any of the
models below.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


def confidence_level_for(score: float, high_threshold: float = 0.75, medium_threshold: float = 0.4) -> ConfidenceLevel:
    """Derive a qualitative confidence bucket from a numeric score.

    Kept as a standalone helper (rather than logic baked into a validator) so
    `vision/confidence.py` can reuse the exact same thresholds/logic when it
    recalibrates scores after grounding.
    """
    if score >= high_threshold:
        return ConfidenceLevel.high
    if score >= medium_threshold:
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


class ExtractedField(BaseModel, Generic[T]):
    """Generic wrapper enforced on every individually extracted attribute.

    Invariant: a null value can NEVER carry a high/medium confidence label.
    This is enforced structurally (not just by convention) via a validator,
    so it is impossible to construct a "confidently unknown" field anywhere
    in the codebase.
    """

    value: Optional[T] = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    reason: str = Field(min_length=1)

    @field_validator("confidence_level")
    @classmethod
    def _null_value_forces_low(cls, v: ConfidenceLevel, info) -> ConfidenceLevel:
        value = info.data.get("value")
        if value is None and v != ConfidenceLevel.low:
            return ConfidenceLevel.low
        return v

    @classmethod
    def unknown(cls, reason: str, confidence: float = 0.05) -> "ExtractedField[T]":
        """Convenience constructor for the canonical 'cannot confidently identify' case."""
        return cls(value=None, confidence=min(confidence, 0.2), confidence_level=ConfidenceLevel.low, reason=reason)

    @classmethod
    def known(cls, value: T, confidence: float, reason: str, high_threshold: float = 0.75, medium_threshold: float = 0.4) -> "ExtractedField[T]":
        return cls(
            value=value,
            confidence=confidence,
            confidence_level=confidence_level_for(confidence, high_threshold, medium_threshold),
            reason=reason,
        )


class ConfidenceFactors(BaseModel):
    """The individual signals `overall_confidence` is derived from, broken
    out so a reviewer can see *why* a score is what it is instead of trusting
    one opaque number.

    `ocr` is a deliberate approximation, not a separate OCR engine: this
    pipeline's vision-language model reads label text jointly with visual
    recognition rather than through a distinct OCR pass, so `ocr` is derived
    from the size-text legibility confidence (the most purely "reading small
    print" field) while `vision` is derived from brand/product recognition
    confidence. See docs/DESIGN_NOTES.md for the buy-vs-build reasoning.
    """

    vision: float = Field(ge=0.0, le=1.0, description="Brand/product visual recognition confidence, pre-corroboration")
    ocr: float = Field(ge=0.0, le=1.0, description="Label/size text legibility confidence (approximated - see class docstring)")
    catalog_match: float = Field(ge=0.0, le=1.0, description="SKU grounding confidence from sku/matcher.py")
    frame_consistency: float = Field(ge=0.0, le=1.0, description="Fraction of analyzed frames this observation was corroborated in")


class ConfidenceBreakdown(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    factors: ConfidenceFactors


class ProductObserved(BaseModel):
    brand: ExtractedField[str]
    product_name: ExtractedField[str]
    size: ExtractedField[str]
    facings: ExtractedField[int]
    shelf_level: ExtractedField[str]  # top | eye-level | middle | bottom
    matched_sku: ExtractedField[str] = Field(
        description="Grounded catalog reference '<id>: <brand> <product_name> <size>', filled by sku/matcher.py"
    )
    overall_confidence: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceBreakdown = Field(description="Same overall score as overall_confidence, plus the factor breakdown")
    evidence: List[str] = Field(default_factory=list, description="Human-readable grounds for (or against) this observation")
    source_frames: List[str] = Field(default_factory=list, description="Frame identifiers this observation was corroborated in")


class OutOfStockSignal(BaseModel):
    location: ExtractedField[str]
    likely_product: ExtractedField[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ShelfPosition(BaseModel):
    level: ExtractedField[str]
    description: ExtractedField[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class Promotion(BaseModel):
    promo_type: ExtractedField[str]
    text_detected: ExtractedField[str]
    associated_product: ExtractedField[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class PricingRead(BaseModel):
    product: ExtractedField[str]
    price: ExtractedField[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ComplianceFlag(BaseModel):
    issue_type: ExtractedField[str]
    description: ExtractedField[str]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ShareOfShelf(BaseModel):
    by_brand: dict[str, float] = Field(default_factory=dict, description="brand -> percentage of counted facings")
    total_facings_counted: int = 0
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


class ConfidenceSummary(BaseModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    frames_analyzed: int = 0
    warnings: List[str] = Field(default_factory=list)


class ShelfAudit(BaseModel):
    account_id: str
    media_reference: str
    media_type: Literal["image", "video"]
    products_observed: List[ProductObserved] = Field(default_factory=list)
    out_of_stock_signals: List[OutOfStockSignal] = Field(default_factory=list)
    shelf_positions: List[ShelfPosition] = Field(default_factory=list)
    promotions: List[Promotion] = Field(default_factory=list)
    pricing_reads: List[PricingRead] = Field(default_factory=list)
    compliance_flags: List[ComplianceFlag] = Field(default_factory=list)
    share_of_shelf: ShareOfShelf
    notes: str = ""
    confidence_summary: ConfidenceSummary
    generated_at: datetime = Field(default_factory=datetime.utcnow)
