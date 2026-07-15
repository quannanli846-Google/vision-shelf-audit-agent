"""Untrusted schema for raw vision-model output.

Nothing in this module is ever persisted or exposed as the final audit
record. It exists solely so `vision/validator.py` has a structured (but
deliberately permissive) shape to parse the model's JSON into before doing
strict, field-by-field validation/coercion into the trusted models in
`models/shelf_audit.py`.

Fields are typed loosely (`Any`) on purpose: a badly-behaved model response
(wrong type, out-of-range confidence, missing reason) should cause that ONE
field to be discarded/downgraded by the validator - not raise an exception
that throws away an entire frame's worth of otherwise-useful data. Only a
totally unparseable response discards the whole frame.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class RawField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Any = None
    confidence: Any = None
    reason: Any = None


class RawProductObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    brand: Optional[RawField] = None
    product_name: Optional[RawField] = None
    size: Optional[RawField] = None
    facings: Optional[RawField] = None
    shelf_level: Optional[RawField] = None


class RawOutOfStockSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: Optional[RawField] = None
    likely_product: Optional[RawField] = None


class RawShelfPosition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: Optional[RawField] = None
    description: Optional[RawField] = None


class RawPromotion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    promo_type: Optional[RawField] = None
    text_detected: Optional[RawField] = None
    associated_product: Optional[RawField] = None


class RawPricingRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product: Optional[RawField] = None
    price: Optional[RawField] = None


class RawComplianceFlag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issue_type: Optional[RawField] = None
    description: Optional[RawField] = None


class RawFrameObservation(BaseModel):
    """The full untrusted shape expected back from one vision-model call."""

    model_config = ConfigDict(extra="ignore")

    products: List[RawProductObservation] = []
    out_of_stock_signals: List[RawOutOfStockSignal] = []
    shelf_positions: List[RawShelfPosition] = []
    promotions: List[RawPromotion] = []
    pricing_reads: List[RawPricingRead] = []
    compliance_flags: List[RawComplianceFlag] = []
    notes: Optional[str] = None
