"""Unit tests for vision/validator.py - the layer that guarantees raw,
untrusted model output can never reach the database unchecked.
"""
import json

from models.raw_observation import RawField
from vision.validator import parse_raw_response, validate_field


class TestParseRawResponse:
    def test_valid_json_matching_schema_parses_successfully(self):
        payload = {
            "products": [
                {
                    "brand": {"value": "Tito's", "confidence": 0.9, "reason": "clear label"},
                    "product_name": {"value": "Handmade Vodka", "confidence": 0.85, "reason": "clear label"},
                    "size": {"value": "750ml", "confidence": 0.7, "reason": "visible"},
                    "facings": {"value": 4, "confidence": 0.8, "reason": "counted"},
                    "shelf_level": {"value": "eye-level", "confidence": 0.6, "reason": "position"},
                }
            ],
            "out_of_stock_signals": [],
            "shelf_positions": [],
            "promotions": [],
            "pricing_reads": [],
            "compliance_flags": [],
            "notes": "test",
        }
        parsed, warnings = parse_raw_response(json.dumps(payload), "frame_0")

        assert parsed is not None
        assert warnings == []
        assert len(parsed.products) == 1
        assert parsed.products[0].brand.value == "Tito's"

    def test_malformed_json_discards_the_whole_frame(self):
        parsed, warnings = parse_raw_response("{not valid json!!", "frame_0")

        assert parsed is None
        assert len(warnings) == 1
        assert "not valid JSON" in warnings[0]
        assert "frame_0" in warnings[0]

    def test_unexpected_top_level_shape_discards_the_whole_frame(self):
        # e.g. the model returned a JSON array instead of an object
        parsed, warnings = parse_raw_response(json.dumps(["unexpected", "shape"]), "frame_1")

        assert parsed is None
        assert len(warnings) == 1

    def test_unknown_extra_keys_are_ignored_not_rejected(self):
        payload = {"products": [], "out_of_stock_signals": [], "shelf_positions": [], "promotions": [],
                   "pricing_reads": [], "compliance_flags": [], "notes": "ok", "some_hallucinated_extra_field": 123}
        parsed, warnings = parse_raw_response(json.dumps(payload), "frame_2")

        assert parsed is not None
        assert warnings == []


class TestValidateField:
    def test_well_formed_field_passes_through(self):
        raw = RawField(value="Tito's", confidence=0.9, reason="clear label")
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.value == "Tito's"
        assert field.confidence == 0.9
        assert field.confidence_level.value == "high"
        assert warnings == []

    def test_missing_field_becomes_unknown(self):
        warnings: list[str] = []
        field = validate_field(None, str, "brand", "frame_0", warnings)

        assert field.value is None
        assert field.confidence_level.value == "low"
        assert "was not present" in field.reason

    def test_wrong_type_value_is_discarded_not_coerced_silently(self):
        raw = RawField(value=12345, confidence=0.8, reason="looks like a brand")  # int where a string is expected
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.value is None
        assert field.confidence_level.value == "low"
        assert any("expected a string" in w for w in warnings)

    def test_out_of_range_confidence_is_clamped(self):
        raw = RawField(value="Tito's", confidence=1.5, reason="clear label")
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.confidence == 1.0
        assert any("clamped" in w for w in warnings)

    def test_negative_confidence_is_clamped(self):
        raw = RawField(value="Tito's", confidence=-0.5, reason="clear label")
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.confidence == 0.0

    def test_missing_reason_gets_a_fallback_and_is_warned_about(self):
        raw = RawField(value="Tito's", confidence=0.8, reason=None)
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.reason  # never empty
        assert any("no reason" in w for w in warnings)

    def test_null_value_is_forced_to_low_confidence_regardless_of_reported_score(self):
        raw = RawField(value=None, confidence=0.95, reason="not visible")
        warnings: list[str] = []
        field = validate_field(raw, str, "brand", "frame_0", warnings)

        assert field.value is None
        assert field.confidence_level.value == "low"
        assert field.confidence <= 0.2

    def test_integer_field_accepts_integral_float(self):
        raw = RawField(value=4.0, confidence=0.7, reason="counted")
        warnings: list[str] = []
        field = validate_field(raw, int, "facings", "frame_0", warnings)

        assert field.value == 4
        assert warnings == []

    def test_integer_field_rejects_non_integral_float(self):
        raw = RawField(value=4.5, confidence=0.7, reason="counted")
        warnings: list[str] = []
        field = validate_field(raw, int, "facings", "frame_0", warnings)

        assert field.value is None
        assert any("expected an integer" in w for w in warnings)

    def test_boolean_is_never_accepted_as_integer(self):
        raw = RawField(value=True, confidence=0.7, reason="counted")
        warnings: list[str] = []
        field = validate_field(raw, int, "facings", "frame_0", warnings)

        assert field.value is None
