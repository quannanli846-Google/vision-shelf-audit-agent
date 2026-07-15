"""Unit tests for the confidence-breakdown/evidence helpers in
vision/extractor.py - the multi-factor confidence calculation and the
human-readable evidence checklist that AuditResultPage renders.

These test the pure helper functions directly with hand-built
`ExtractedField`s rather than running the full `run_extraction` pipeline, so
they stay fast and don't need a vision client or media file.
"""
from __future__ import annotations

from models.shelf_audit import ExtractedField
from vision.extractor import _build_confidence_breakdown, _build_evidence


def _field(value, confidence: float, reason: str = "test reason") -> ExtractedField:
    return ExtractedField.known(value=value, confidence=confidence, reason=reason)


class TestBuildConfidenceBreakdown:
    def test_overall_is_passed_through_unchanged(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.8), _field("750ml", 0.7)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.9)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.833, corroborated_frame_count=1, frames_analyzed=1)

        assert breakdown.overall == 0.833

    def test_vision_factor_is_mean_of_brand_and_product_name_confidence(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.7), _field("750ml", 0.5)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.6)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.7, corroborated_frame_count=1, frames_analyzed=1)

        assert breakdown.factors.vision == 0.8

    def test_ocr_factor_is_size_field_confidence(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.9), _field("750ml", 0.42)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.6)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.7, corroborated_frame_count=1, frames_analyzed=1)

        assert breakdown.factors.ocr == 0.42

    def test_catalog_match_factor_is_matched_sku_confidence(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.9), _field("750ml", 0.9)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.63)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.7, corroborated_frame_count=1, frames_analyzed=1)

        assert breakdown.factors.catalog_match == 0.63

    def test_frame_consistency_is_corroborated_over_analyzed_frames(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.9), _field("750ml", 0.9)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.9)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.9, corroborated_frame_count=3, frames_analyzed=5)

        assert breakdown.factors.frame_consistency == 0.6

    def test_frame_consistency_is_capped_at_one(self):
        brand, product_name, size = _field("Tito's", 0.9), _field("Vodka", 0.9), _field("750ml", 0.9)
        matched_sku = _field("1: Tito's Vodka (750ml)", 0.9)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 0.9, corroborated_frame_count=8, frames_analyzed=5)

        assert breakdown.factors.frame_consistency == 1.0

    def test_all_factors_stay_within_zero_and_one(self):
        brand, product_name, size = _field("Tito's", 1.0), _field("Vodka", 1.0), _field("750ml", 1.0)
        matched_sku = _field("1: Tito's Vodka (750ml)", 1.0)

        breakdown = _build_confidence_breakdown(brand, product_name, size, matched_sku, 1.0, corroborated_frame_count=10, frames_analyzed=1)

        for factor_value in breakdown.factors.model_dump().values():
            assert 0.0 <= factor_value <= 1.0


class TestBuildEvidence:
    def test_identified_product_gets_positive_evidence_lines(self):
        brand = _field("Tito's", 0.9, "brand label clearly visible")
        product_name = _field("Handmade Vodka", 0.88, "product text legible")
        matched_sku = _field("1: Tito's Handmade Vodka (750ml)", 0.9, "matched catalog alias")

        evidence = _build_evidence(brand, product_name, matched_sku, source_frame_count=1)

        assert any("Tito's" in line and "identified" in line for line in evidence)
        assert any("Handmade Vodka" in line and "legible" in line for line in evidence)
        assert any("Matched catalog entry" in line for line in evidence)

    def test_unidentified_product_gets_honest_negative_evidence_not_a_guess(self):
        brand = ExtractedField.unknown(reason="label obscured by glare")
        product_name = ExtractedField.unknown(reason="product text not visible")
        matched_sku = ExtractedField.unknown(reason="no brand or product name to match against")

        evidence = _build_evidence(brand, product_name, matched_sku, source_frame_count=1)

        assert any("not identified" in line for line in evidence)
        assert any("not legible" in line for line in evidence)
        assert any("No catalog match" in line for line in evidence)
        # Never fabricate a brand/product name string when the value is null.
        assert not any("Tito's" in line for line in evidence)

    def test_multi_frame_corroboration_is_called_out(self):
        brand = _field("Corona", 0.85)
        product_name = _field("Extra", 0.8)
        matched_sku = _field("2: Corona Extra (12pk)", 0.8)

        evidence = _build_evidence(brand, product_name, matched_sku, source_frame_count=3)

        assert any("3 frames" in line for line in evidence)

    def test_single_frame_does_not_claim_cross_frame_corroboration(self):
        brand = _field("Corona", 0.85)
        product_name = _field("Extra", 0.8)
        matched_sku = _field("2: Corona Extra (12pk)", 0.8)

        evidence = _build_evidence(brand, product_name, matched_sku, source_frame_count=1)

        assert not any("frames" in line for line in evidence)
