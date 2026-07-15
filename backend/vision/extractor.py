"""Orchestrates the end-to-end vision pipeline for one uploaded media asset.

Image path: the single image goes directly to the vision model - no frame
extraction/quality filtering involved.
Video path: `video/frame_extractor.py` samples candidate frames, then
`video/quality_filter.py` drops blurry/duplicate frames and picks a small,
time-diverse set - only THAT set is sent to the (expensive) vision model.

Every frame's raw model response is parsed through `vision/validator.py`
before any of it is used. Multi-frame observations of "the same product" are
merged and corroboration-boosted via `vision/confidence.py`. Grounding
against the SKU catalog happens once, on the merged/representative values,
via `sku/matcher.py`. The only object this module returns is a fully
validated, grounded, calibrated `ShelfAudit` - never raw model output.
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from config import Settings
from models.raw_observation import RawFrameObservation
from models.shelf_audit import (
    ComplianceFlag,
    ConfidenceBreakdown,
    ConfidenceFactors,
    ExtractedField,
    OutOfStockSignal,
    PricingRead,
    ProductObserved,
    Promotion,
    ShareOfShelf,
    ShelfAudit,
    ShelfPosition,
)
from sku.catalog import ProductCatalog
from sku.matcher import match_product
from vision import confidence as confidence_mod
from vision import validator
from vision.client import VisionClient
from video.frame_extractor import SampledFrame, extract_frames
from video.quality_filter import (
    FrameQualityRecord,
    QualityFilterResult,
    compute_blur_score,
    compute_brightness_score,
    compute_quality_score,
    filter_and_select,
    make_thumbnail_data_uri,
)

ProgressCallback = Optional[Callable[[str], None]]


@dataclass
class _FrameInput:
    frame_id: str
    image_bytes: bytes


@dataclass
class PipelineTrace:
    media_type: str
    vision_provider: str = "Unknown Vision Provider"
    frames_sampled: int = 0
    frames_kept: int = 0
    frames_selected: list[str] = field(default_factory=list)
    frames_rejected: list[dict] = field(default_factory=list)
    frame_quality_records: list[dict] = field(default_factory=list)
    raw_model_outputs: dict[str, str] = field(default_factory=dict)
    validation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "media_type": self.media_type,
            "vision_provider": self.vision_provider,
            "frames_sampled": self.frames_sampled,
            "frames_kept": self.frames_kept,
            "frames_selected": self.frames_selected,
            "frames_rejected": self.frames_rejected,
            "frame_quality_records": self.frame_quality_records,
            "raw_model_outputs": self.raw_model_outputs,
            "validation_warnings": self.validation_warnings,
        }


def _select_frame_inputs(
    media_path: Path,
    media_type: str,
    settings: Settings,
    trace: PipelineTrace,
    on_progress: ProgressCallback,
) -> list[_FrameInput]:
    if media_type == "image":
        if on_progress:
            on_progress("analyzing image")
        image_bytes = media_path.read_bytes()

        # Even a single still image gets a real quality record (blur/brightness/
        # quality_score + thumbnail) rather than a hardcoded "trust it blindly"
        # placeholder - this is what lets the "Analyzed Media" UI treat images
        # and video frames uniformly instead of as two different code paths.
        decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is not None:
            blur_score = compute_blur_score(decoded)
            brightness_score = compute_brightness_score(decoded)
            quality_score = compute_quality_score(blur_score, brightness_score, settings.video_blur_variance_threshold)
            record = FrameQualityRecord(
                frame_id="image",
                timestamp_sec=0.0,
                blur_score=blur_score,
                brightness_score=brightness_score,
                quality_score=quality_score,
                selected=True,
                thumbnail=make_thumbnail_data_uri(decoded),
            )
            trace.frame_quality_records = [record.to_dict()]

        trace.frames_sampled = 1
        trace.frames_kept = 1
        trace.frames_selected = ["image"]
        return [_FrameInput(frame_id="image", image_bytes=image_bytes)]

    if on_progress:
        on_progress("extracting video frames")
    sampled: list[SampledFrame] = extract_frames(
        media_path, sample_fps=settings.video_sample_fps, max_frames=settings.video_max_sampled_frames
    )

    if on_progress:
        on_progress("filtering low-quality frames")
    result: QualityFilterResult = filter_and_select(
        sampled,
        blur_variance_threshold=settings.video_blur_variance_threshold,
        duplicate_hash_threshold=settings.video_duplicate_hash_threshold,
        max_frames_for_vision=settings.video_max_frames_for_vision,
        dark_brightness_threshold=settings.video_dark_brightness_threshold,
        overexposed_brightness_threshold=settings.video_overexposed_brightness_threshold,
        gallery_thumbnail_max=settings.video_gallery_thumbnail_max,
    )
    trace_dict = result.to_trace_dict()
    trace.frames_sampled = result.frames_sampled
    trace.frames_kept = result.frames_kept
    trace.frames_selected = [f.frame_id for f in result.selected]
    trace.frames_rejected = trace_dict["frames_rejected"]
    trace.frame_quality_records = trace_dict["frame_quality_records"]

    return [_FrameInput(frame_id=f.frame_id, image_bytes=f.to_jpeg_bytes()) for f in result.selected]


@dataclass
class _FieldObservation:
    frame_id: str
    field: ExtractedField


@dataclass
class _ProductGroup:
    key: str
    brand: list[_FieldObservation] = field(default_factory=list)
    product_name: list[_FieldObservation] = field(default_factory=list)
    size: list[_FieldObservation] = field(default_factory=list)
    facings: list[_FieldObservation] = field(default_factory=list)
    shelf_level: list[_FieldObservation] = field(default_factory=list)


def _group_key(brand: ExtractedField, product_name: ExtractedField) -> str:
    b = (brand.value or "").strip().lower()
    p = (product_name.value or "").strip().lower()
    if not b and not p:
        return f"__unidentified_{id(brand)}"
    return f"{b}::{p}"


def _pick_representative(observations: list[_FieldObservation], settings: Settings) -> ExtractedField:
    non_null = [o for o in observations if o.field.value is not None]
    if not non_null:
        return observations[0].field if observations else ExtractedField.unknown("no observations for this field")

    best = max(non_null, key=lambda o: o.field.confidence)
    if isinstance(best.field.value, (int, float)) and not isinstance(best.field.value, bool):
        corroborators = [o for o in non_null if o.field.value == best.field.value]
    else:
        corroborators = [o for o in non_null if str(o.field.value).strip().lower() == str(best.field.value).strip().lower()]

    return confidence_mod.apply_corroboration_boost(
        best.field,
        corroboration_count=len(corroborators),
        high_threshold=settings.confidence_high_threshold,
        medium_threshold=settings.confidence_medium_threshold,
    )


def _build_confidence_breakdown(
    brand: ExtractedField,
    product_name: ExtractedField,
    size: ExtractedField,
    matched_sku: ExtractedField,
    overall_confidence: float,
    corroborated_frame_count: int,
    frames_analyzed: int,
) -> ConfidenceBreakdown:
    """Explode the single `overall_confidence` number into the factors that
    fed it, so a reviewer sees *why* a score is what it is. `ocr` and
    `vision` are approximations (see `ConfidenceFactors` docstring) - not a
    literal separate OCR pass - everything here is derived from scores the
    pipeline already computed, never invented.
    """
    vision_factor = round((brand.confidence + product_name.confidence) / 2, 3)
    ocr_factor = round(size.confidence, 3)
    catalog_match_factor = round(matched_sku.confidence, 3)
    frame_consistency_factor = round(min(corroborated_frame_count / max(frames_analyzed, 1), 1.0), 3)

    return ConfidenceBreakdown(
        overall=overall_confidence,
        factors=ConfidenceFactors(
            vision=vision_factor,
            ocr=ocr_factor,
            catalog_match=catalog_match_factor,
            frame_consistency=frame_consistency_factor,
        ),
    )


def _build_evidence(
    brand: ExtractedField,
    product_name: ExtractedField,
    matched_sku: ExtractedField,
    source_frame_count: int,
) -> list[str]:
    """Human-readable checklist grounded ONLY in reasons the pipeline already
    validated - never a new claim invented for the UI. Mixes positive and
    negative evidence on purpose: "the system knows what it knows and what
    it does not know" means showing both.
    """
    evidence: list[str] = []
    evidence.append(f"Brand '{brand.value}' identified - {brand.reason}" if brand.value else f"Brand not identified - {brand.reason}")
    evidence.append(
        f"Product name '{product_name.value}' legible - {product_name.reason}"
        if product_name.value
        else f"Product name not legible - {product_name.reason}"
    )
    evidence.append(f"Matched catalog entry - {matched_sku.reason}" if matched_sku.value else f"No catalog match - {matched_sku.reason}")
    if source_frame_count > 1:
        evidence.append(f"Detected independently across {source_frame_count} frames")
    return evidence


def _merge_products(
    per_frame_products: list[tuple[str, list[dict[str, ExtractedField]]]],
    catalog: ProductCatalog,
    settings: Settings,
    frames_analyzed: int = 1,
) -> list[ProductObserved]:
    groups: dict[str, _ProductGroup] = {}
    group_frames: dict[str, set[str]] = {}

    for frame_id, products in per_frame_products:
        for p in products:
            key = _group_key(p["brand"], p["product_name"])
            group = groups.setdefault(key, _ProductGroup(key=key))
            group.brand.append(_FieldObservation(frame_id, p["brand"]))
            group.product_name.append(_FieldObservation(frame_id, p["product_name"]))
            group.size.append(_FieldObservation(frame_id, p["size"]))
            group.facings.append(_FieldObservation(frame_id, p["facings"]))
            group.shelf_level.append(_FieldObservation(frame_id, p["shelf_level"]))
            group_frames.setdefault(key, set()).add(frame_id)

    merged: list[ProductObserved] = []
    for key, group in groups.items():
        brand = _pick_representative(group.brand, settings)
        product_name = _pick_representative(group.product_name, settings)
        size = _pick_representative(group.size, settings)
        facings = _pick_representative(group.facings, settings)
        shelf_level = _pick_representative(group.shelf_level, settings)

        matched_sku = match_product(
            brand.value,
            product_name.value,
            size.value,
            catalog,
            high_threshold=settings.sku_match_high_threshold,
            low_threshold=settings.sku_match_low_threshold,
            ambiguous_margin=settings.sku_match_ambiguous_margin,
            confidence_high_threshold=settings.confidence_high_threshold,
            confidence_medium_threshold=settings.confidence_medium_threshold,
        )

        overall = confidence_mod.compute_item_overall_confidence([brand, product_name, size, facings, shelf_level, matched_sku])
        source_frames = sorted(group_frames.get(key, set()))
        confidence_breakdown = _build_confidence_breakdown(
            brand, product_name, size, matched_sku, overall, len(source_frames), frames_analyzed
        )
        evidence = _build_evidence(brand, product_name, matched_sku, len(source_frames))

        merged.append(
            ProductObserved(
                brand=brand,
                product_name=product_name,
                size=size,
                facings=facings,
                shelf_level=shelf_level,
                matched_sku=matched_sku,
                overall_confidence=overall,
                confidence=confidence_breakdown,
                evidence=evidence,
                source_frames=source_frames,
            )
        )

    merged.sort(key=lambda p: p.overall_confidence, reverse=True)
    return merged


def _build_share_of_shelf(products: list[ProductObserved]) -> ShareOfShelf:
    facings_by_brand: dict[str, int] = {}
    total = 0
    counted_confidences: list[float] = []

    for p in products:
        if p.facings.value is None:
            continue
        brand_label = p.brand.value or "Unidentified"
        facings_by_brand[brand_label] = facings_by_brand.get(brand_label, 0) + p.facings.value
        total += p.facings.value
        counted_confidences.append(p.facings.confidence)

    if total == 0:
        return ShareOfShelf(
            by_brand={},
            total_facings_counted=0,
            confidence=0.05,
            reason="no product facings could be confidently counted in the analyzed frame(s)",
        )

    by_brand_pct = {brand: round((count / total) * 100, 1) for brand, count in facings_by_brand.items()}
    avg_confidence = round(sum(counted_confidences) / len(counted_confidences), 3)
    excluded = len(products) - len(counted_confidences)
    reason = f"computed from {len(counted_confidences)} product(s) with a countable facings value"
    if excluded:
        reason += f"; {excluded} product(s) excluded because facings could not be confidently counted"

    return ShareOfShelf(by_brand=by_brand_pct, total_facings_counted=total, confidence=avg_confidence, reason=reason)


def _validate_frame_products(raw: RawFrameObservation, frame_id: str, settings: Settings, warnings: list[str]) -> list[dict[str, ExtractedField]]:
    items = []
    for raw_product in raw.products:
        items.append(
            {
                "brand": validator.validate_field(raw_product.brand, str, "brand", frame_id, warnings, settings.confidence_high_threshold, settings.confidence_medium_threshold),
                "product_name": validator.validate_field(raw_product.product_name, str, "product_name", frame_id, warnings, settings.confidence_high_threshold, settings.confidence_medium_threshold),
                "size": validator.validate_field(raw_product.size, str, "size", frame_id, warnings, settings.confidence_high_threshold, settings.confidence_medium_threshold),
                "facings": validator.validate_field(raw_product.facings, int, "facings", frame_id, warnings, settings.confidence_high_threshold, settings.confidence_medium_threshold),
                "shelf_level": validator.validate_field(raw_product.shelf_level, str, "shelf_level", frame_id, warnings, settings.confidence_high_threshold, settings.confidence_medium_threshold),
            }
        )
    return items


def run_extraction(
    media_path: Path,
    media_type: str,
    account_id: str,
    media_reference: str,
    vision_client: VisionClient,
    catalog: ProductCatalog,
    settings: Settings,
    on_progress: ProgressCallback = None,
) -> tuple[ShelfAudit, dict]:
    trace = PipelineTrace(media_type=media_type, vision_provider=vision_client.provider_name)
    frame_inputs = _select_frame_inputs(media_path, media_type, settings, trace, on_progress)

    warnings: list[str] = []
    per_frame_products: list[tuple[str, list[dict[str, ExtractedField]]]] = []
    out_of_stock: list[OutOfStockSignal] = []
    shelf_positions: list[ShelfPosition] = []
    promotions: list[Promotion] = []
    pricing_reads: list[PricingRead] = []
    compliance_flags: list[ComplianceFlag] = []
    notes_parts: list[str] = []

    ht, mt = settings.confidence_high_threshold, settings.confidence_medium_threshold

    for idx, frame_input in enumerate(frame_inputs):
        if on_progress:
            on_progress(f"analyzing frame {idx + 1}/{len(frame_inputs)}")

        raw_text = vision_client.analyze_frame(frame_input.image_bytes, frame_input.frame_id)
        trace.raw_model_outputs[frame_input.frame_id] = raw_text

        raw_obs, parse_warnings = validator.parse_raw_response(raw_text, frame_input.frame_id)
        warnings.extend(parse_warnings)
        if raw_obs is None:
            continue

        per_frame_products.append((frame_input.frame_id, _validate_frame_products(raw_obs, frame_input.frame_id, settings, warnings)))

        for oos in raw_obs.out_of_stock_signals:
            location = validator.validate_field(oos.location, str, "location", frame_input.frame_id, warnings, ht, mt)
            likely = validator.validate_field(oos.likely_product, str, "likely_product", frame_input.frame_id, warnings, ht, mt)
            out_of_stock.append(OutOfStockSignal(location=location, likely_product=likely, overall_confidence=confidence_mod.compute_item_overall_confidence([location, likely])))

        for sp in raw_obs.shelf_positions:
            level = validator.validate_field(sp.level, str, "level", frame_input.frame_id, warnings, ht, mt)
            desc = validator.validate_field(sp.description, str, "description", frame_input.frame_id, warnings, ht, mt)
            shelf_positions.append(ShelfPosition(level=level, description=desc, overall_confidence=confidence_mod.compute_item_overall_confidence([level, desc])))

        for promo in raw_obs.promotions:
            promo_type = validator.validate_field(promo.promo_type, str, "promo_type", frame_input.frame_id, warnings, ht, mt)
            text_detected = validator.validate_field(promo.text_detected, str, "text_detected", frame_input.frame_id, warnings, ht, mt)
            associated = validator.validate_field(promo.associated_product, str, "associated_product", frame_input.frame_id, warnings, ht, mt)
            promotions.append(
                Promotion(
                    promo_type=promo_type,
                    text_detected=text_detected,
                    associated_product=associated,
                    overall_confidence=confidence_mod.compute_item_overall_confidence([promo_type, text_detected, associated]),
                )
            )

        for pricing in raw_obs.pricing_reads:
            product_field = validator.validate_field(pricing.product, str, "product", frame_input.frame_id, warnings, ht, mt)
            price_field = validator.validate_field(pricing.price, str, "price", frame_input.frame_id, warnings, ht, mt)
            pricing_reads.append(PricingRead(product=product_field, price=price_field, overall_confidence=confidence_mod.compute_item_overall_confidence([product_field, price_field])))

        for flag in raw_obs.compliance_flags:
            issue_type = validator.validate_field(flag.issue_type, str, "issue_type", frame_input.frame_id, warnings, ht, mt)
            description = validator.validate_field(flag.description, str, "description", frame_input.frame_id, warnings, ht, mt)
            compliance_flags.append(ComplianceFlag(issue_type=issue_type, description=description, overall_confidence=confidence_mod.compute_item_overall_confidence([issue_type, description])))

        if raw_obs.notes:
            notes_parts.append(f"[{frame_input.frame_id}] {raw_obs.notes}")

    if on_progress:
        on_progress("grounding products against SKU catalog")
    products_observed = _merge_products(per_frame_products, catalog, settings, frames_analyzed=len(frame_inputs))

    if on_progress:
        on_progress("calibrating confidence")
    share_of_shelf = _build_share_of_shelf(products_observed)

    all_fields: list[ExtractedField] = []
    for p in products_observed:
        all_fields.extend([p.brand, p.product_name, p.size, p.facings, p.shelf_level, p.matched_sku])
    for lst, attrs in [
        (out_of_stock, ("location", "likely_product")),
        (shelf_positions, ("level", "description")),
        (promotions, ("promo_type", "text_detected", "associated_product")),
        (pricing_reads, ("product", "price")),
        (compliance_flags, ("issue_type", "description")),
    ]:
        for item in lst:
            all_fields.extend(getattr(item, attr) for attr in attrs)

    products_unmatched = sum(1 for p in products_observed if p.matched_sku.value is None)
    confidence_summary = confidence_mod.summarize_confidence(
        all_fields,
        frames_analyzed=len(frame_inputs),
        products_total=len(products_observed),
        products_unmatched=products_unmatched,
        high_threshold=ht,
        medium_threshold=mt,
    )
    confidence_summary.warnings.extend(f"validation: {w}" for w in warnings[:10])
    trace.validation_warnings = warnings

    audit = ShelfAudit(
        account_id=account_id,
        media_reference=media_reference,
        media_type=media_type,  # type: ignore[arg-type]
        products_observed=products_observed,
        out_of_stock_signals=out_of_stock,
        shelf_positions=shelf_positions,
        promotions=promotions,
        pricing_reads=pricing_reads,
        compliance_flags=compliance_flags,
        share_of_shelf=share_of_shelf,
        notes=" | ".join(notes_parts) if notes_parts else "No additional notes.",
        confidence_summary=confidence_summary,
    )

    return audit, trace.to_dict()
