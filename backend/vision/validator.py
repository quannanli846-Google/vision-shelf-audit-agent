"""Validation layer: the single choke point through which raw, untrusted
vision-model JSON must pass before any of its data can be used.

Nothing downstream of this module ever sees a raw model value directly.
Malformed JSON discards the whole frame (logged as a warning). A malformed
individual field (wrong type, missing confidence, out-of-range confidence,
missing reason) discards/downgrades only that one field - never crashes the
whole extraction - by coercing it into a null-valued, low-confidence
`ExtractedField` with an explanatory reason.
"""
from __future__ import annotations

import json
from typing import Optional, Type, TypeVar

from pydantic import ValidationError

from models.raw_observation import RawField, RawFrameObservation
from models.shelf_audit import ConfidenceLevel, ExtractedField, confidence_level_for

T = TypeVar("T", str, int)

DEFAULT_LOW_CONFIDENCE = 0.15


def parse_raw_response(raw_text: str, frame_id: str) -> tuple[Optional[RawFrameObservation], list[str]]:
    """Stage 1: parse the model's raw text into the untrusted RawFrameObservation shape.

    Returns (None, [warning]) if the response can't be parsed/doesn't match the
    expected structure at all - the caller must then discard this frame entirely.
    """
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [f"{frame_id}: model response was not valid JSON ({exc}); entire frame discarded"]

    try:
        return RawFrameObservation.model_validate(data), []
    except ValidationError as exc:
        return None, [
            f"{frame_id}: model response did not match the expected schema shape "
            f"({exc.error_count()} structural errors); entire frame discarded"
        ]


def _coerce_value(raw_value, expected_type: Type[T], field_name: str, frame_id: str, warnings: list[str]) -> Optional[T]:
    if raw_value is None:
        return None
    if expected_type is str:
        if isinstance(raw_value, str):
            stripped = raw_value.strip()
            return stripped or None  # type: ignore[return-value]
        warnings.append(f"{frame_id}: '{field_name}' expected a string but got {type(raw_value).__name__}; value discarded")
        return None
    if expected_type is int:
        if isinstance(raw_value, bool):
            warnings.append(f"{frame_id}: '{field_name}' expected an integer but got a boolean; value discarded")
            return None
        if isinstance(raw_value, int):
            return raw_value  # type: ignore[return-value]
        if isinstance(raw_value, float) and raw_value.is_integer():
            return int(raw_value)  # type: ignore[return-value]
        warnings.append(f"{frame_id}: '{field_name}' expected an integer but got {type(raw_value).__name__}; value discarded")
        return None
    return raw_value


def _coerce_confidence(raw_confidence, field_name: str, frame_id: str, warnings: list[str]) -> float:
    if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool):
        clamped = max(0.0, min(1.0, float(raw_confidence)))
        if abs(clamped - float(raw_confidence)) > 1e-9:
            warnings.append(f"{frame_id}: '{field_name}' confidence {raw_confidence} out of [0,1]; clamped to {clamped}")
        return clamped
    warnings.append(f"{frame_id}: '{field_name}' confidence missing or invalid; defaulted to low")
    return DEFAULT_LOW_CONFIDENCE


def _coerce_reason(raw_reason, field_name: str, frame_id: str, warnings: list[str]) -> str:
    if isinstance(raw_reason, str) and raw_reason.strip():
        return raw_reason.strip()
    warnings.append(f"{frame_id}: '{field_name}' had no reason from the model")
    return "model did not provide a reason for this field"


def validate_field(
    raw_field: Optional[RawField],
    expected_type: Type[T],
    field_name: str,
    frame_id: str,
    warnings: list[str],
    high_threshold: float = 0.75,
    medium_threshold: float = 0.4,
) -> ExtractedField:
    """Stage 2: coerce one untrusted RawField into a trusted ExtractedField.

    This is the function that structurally guarantees the "never hallucinate"
    contract: any field that fails type/range/shape checks is forced to
    value=None + confidence_level=low with a reason explaining what went wrong,
    rather than being passed through or dropped silently.
    """
    if raw_field is None:
        return ExtractedField.unknown(reason=f"'{field_name}' was not present in the model output", confidence=0.05)

    value = _coerce_value(raw_field.value, expected_type, field_name, frame_id, warnings)
    confidence = _coerce_confidence(raw_field.confidence, field_name, frame_id, warnings)
    reason = _coerce_reason(raw_field.reason, field_name, frame_id, warnings)

    if value is None:
        return ExtractedField(value=None, confidence=min(confidence, 0.2), confidence_level=ConfidenceLevel.low, reason=reason)

    return ExtractedField(
        value=value,
        confidence=confidence,
        confidence_level=confidence_level_for(confidence, high_threshold, medium_threshold),
        reason=reason,
    )
