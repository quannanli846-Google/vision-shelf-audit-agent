"""Unit tests for vision/confidence.py - calibration and aggregation."""
from models.shelf_audit import ConfidenceLevel, ExtractedField, confidence_level_for
from vision.confidence import (
    apply_corroboration_boost,
    compute_item_overall_confidence,
    summarize_confidence,
)


class TestConfidenceLevelFor:
    def test_high_medium_low_buckets(self):
        assert confidence_level_for(0.9) == ConfidenceLevel.high
        assert confidence_level_for(0.75) == ConfidenceLevel.high
        assert confidence_level_for(0.5) == ConfidenceLevel.medium
        assert confidence_level_for(0.4) == ConfidenceLevel.medium
        assert confidence_level_for(0.1) == ConfidenceLevel.low

    def test_respects_custom_thresholds(self):
        assert confidence_level_for(0.6, high_threshold=0.5, medium_threshold=0.3) == ConfidenceLevel.high


class TestExtractedFieldNullInvariant:
    def test_null_value_always_forces_low_confidence_level(self):
        field = ExtractedField(value=None, confidence=0.95, confidence_level=ConfidenceLevel.high, reason="test")
        assert field.confidence_level == ConfidenceLevel.low

    def test_unknown_constructor_is_always_low(self):
        field = ExtractedField.unknown(reason="not visible")
        assert field.value is None
        assert field.confidence_level == ConfidenceLevel.low
        assert field.confidence <= 0.2


class TestCorroborationBoost:
    def test_no_boost_for_single_observation(self):
        field = ExtractedField.known("Tito's", 0.6, "seen once")
        boosted = apply_corroboration_boost(field, corroboration_count=1)
        assert boosted.confidence == field.confidence

    def test_boost_increases_with_more_corroborating_frames(self):
        field = ExtractedField.known("Tito's", 0.6, "seen in this frame")
        boosted_twice = apply_corroboration_boost(field, corroboration_count=2)
        boosted_thrice = apply_corroboration_boost(field, corroboration_count=3)

        assert boosted_twice.confidence > field.confidence
        assert boosted_thrice.confidence > boosted_twice.confidence
        assert "corroborated across" in boosted_thrice.reason

    def test_boost_never_exceeds_cap(self):
        field = ExtractedField.known("Tito's", 0.95, "seen")
        boosted = apply_corroboration_boost(field, corroboration_count=20)
        assert boosted.confidence <= 0.97

    def test_null_values_are_never_boosted(self):
        field = ExtractedField.unknown(reason="not visible")
        boosted = apply_corroboration_boost(field, corroboration_count=5)
        assert boosted.value is None
        assert boosted.confidence == field.confidence


class TestItemOverallConfidence:
    def test_mean_of_field_confidences(self):
        fields = [
            ExtractedField.known("a", 0.8, "r"),
            ExtractedField.known("b", 0.6, "r"),
            ExtractedField.unknown("not visible", confidence=0.1),
        ]
        overall = compute_item_overall_confidence(fields)
        assert overall == round((0.8 + 0.6 + 0.1) / 3, 3)

    def test_empty_list_returns_zero(self):
        assert compute_item_overall_confidence([]) == 0.0


class TestSummarizeConfidence:
    def test_bucket_counts_and_overall(self):
        fields = [
            ExtractedField.known("a", 0.9, "r"),  # high
            ExtractedField.known("b", 0.5, "r"),  # medium
            ExtractedField.unknown("not visible"),  # low
        ]
        summary = summarize_confidence(fields, frames_analyzed=3, products_total=2, products_unmatched=1)

        assert summary.high_count == 1
        assert summary.medium_count == 1
        assert summary.low_count == 1
        assert summary.frames_analyzed == 3

    def test_warns_about_unmatched_products(self):
        fields = [ExtractedField.known("a", 0.9, "r")]
        summary = summarize_confidence(fields, frames_analyzed=2, products_total=4, products_unmatched=3)
        assert any("could not be matched to the reference catalog" in w for w in summary.warnings)

    def test_warns_about_single_frame_analysis(self):
        fields = [ExtractedField.known("a", 0.9, "r")]
        summary = summarize_confidence(fields, frames_analyzed=1, products_total=1, products_unmatched=0)
        assert any("single frame" in w for w in summary.warnings)

    def test_no_fields_produces_zero_confidence_and_a_warning(self):
        summary = summarize_confidence([], frames_analyzed=1, products_total=0, products_unmatched=0)
        assert summary.overall_confidence == 0.0
        assert any("No fields could be extracted" in w for w in summary.warnings)
