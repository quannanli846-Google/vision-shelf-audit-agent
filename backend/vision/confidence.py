"""Confidence calibration: cross-frame corroboration boosting and audit-level
aggregation/summarization.

Field-level confidence assigned by the model (via `vision/validator.py`) is
the base signal. This module adjusts it based on evidence the model itself
can't see - e.g. whether the same product was independently observed in
multiple frames of a video - and rolls everything up into a single
`ConfidenceSummary` with plain-language warnings for the UI.

(SKU-grounding ambiguity penalties live in `sku/matcher.py`, since that is
the module that actually knows about match-score margins - keeping each
calibration rule next to the domain logic it depends on.)
"""
from __future__ import annotations

from models.shelf_audit import ConfidenceLevel, ConfidenceSummary, ExtractedField, confidence_level_for

CORROBORATION_STEP = 0.03
CORROBORATION_MAX_BOOST = 0.15
CORROBORATION_CONFIDENCE_CAP = 0.97


def apply_corroboration_boost(
    field: ExtractedField,
    corroboration_count: int,
    high_threshold: float = 0.75,
    medium_threshold: float = 0.4,
) -> ExtractedField:
    """Boost confidence when a field's value was independently observed across
    multiple frames of a video. Never applied to null values - there is no
    such thing as "confidently corroborated absence" here.
    """
    if field.value is None or corroboration_count <= 1:
        return field

    boost = min(CORROBORATION_STEP * (corroboration_count - 1), CORROBORATION_MAX_BOOST)
    new_confidence = min(field.confidence + boost, CORROBORATION_CONFIDENCE_CAP)
    return ExtractedField(
        value=field.value,
        confidence=round(new_confidence, 3),
        confidence_level=confidence_level_for(new_confidence, high_threshold, medium_threshold),
        reason=f"{field.reason} (corroborated across {corroboration_count} frames)",
    )


def compute_item_overall_confidence(fields: list[ExtractedField]) -> float:
    """Aggregate an item's (e.g. one ProductObserved's) field confidences into
    a single overall score. Plain mean keeps this transparent/predictable -
    no hidden weighting a reviewer can't reconstruct by hand.
    """
    if not fields:
        return 0.0
    return round(sum(f.confidence for f in fields) / len(fields), 3)


def summarize_confidence(
    all_fields: list[ExtractedField],
    frames_analyzed: int,
    products_total: int,
    products_unmatched: int,
    high_threshold: float = 0.75,
    medium_threshold: float = 0.4,
) -> ConfidenceSummary:
    high = sum(1 for f in all_fields if f.confidence_level == ConfidenceLevel.high)
    medium = sum(1 for f in all_fields if f.confidence_level == ConfidenceLevel.medium)
    low = sum(1 for f in all_fields if f.confidence_level == ConfidenceLevel.low)
    overall = round(sum(f.confidence for f in all_fields) / len(all_fields), 3) if all_fields else 0.0

    warnings: list[str] = []
    if products_total > 0 and products_unmatched > 0:
        warnings.append(f"{products_unmatched} of {products_total} products could not be matched to the reference catalog")
    if frames_analyzed <= 1:
        warnings.append("Only a single frame was analyzed - confidence may not reflect the full shelf")
    if all_fields and low > (high + medium):
        warnings.append("More than half of extracted fields have low confidence - treat this audit as preliminary")
    if not all_fields:
        warnings.append("No fields could be extracted at all from the supplied media")

    return ConfidenceSummary(
        overall_confidence=overall,
        high_count=high,
        medium_count=medium,
        low_count=low,
        frames_analyzed=frames_analyzed,
        warnings=warnings,
    )
