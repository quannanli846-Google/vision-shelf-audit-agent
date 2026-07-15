"""SKU grounding: fuzzy-matches vision-extracted brand/product/size against the
reference catalog and returns a properly uncertainty-aware `ExtractedField`.

Never guesses: a low top score returns null with "no catalog match found";
two closely-scored candidates return null with "ambiguous match" rather than
silently picking one. This is what "grounding observations against a product
catalog" means in practice - the field can only be confidently populated when
the catalog genuinely supports it.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from models.shelf_audit import ExtractedField, confidence_level_for
from sku.catalog import CatalogEntry, ProductCatalog


@dataclass
class MatchCandidate:
    entry: CatalogEntry
    score: float  # rapidfuzz score, 0-100


def _best_candidates(query: str, catalog: ProductCatalog, limit: int = 3) -> list[MatchCandidate]:
    scored = [
        MatchCandidate(entry=entry, score=max(fuzz.WRatio(query, s) for s in entry.search_strings))
        for entry in catalog.entries
    ]
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:limit]


def match_product(
    brand: str | None,
    product_name: str | None,
    size: str | None,
    catalog: ProductCatalog,
    high_threshold: float = 88.0,
    low_threshold: float = 60.0,
    ambiguous_margin: float = 5.0,
    confidence_high_threshold: float = 0.75,
    confidence_medium_threshold: float = 0.4,
) -> ExtractedField:
    if not brand and not product_name:
        return ExtractedField.unknown(
            reason="no brand or product name was extracted, so there is nothing to match against the catalog",
            confidence=0.05,
        )

    if catalog.is_empty():
        return ExtractedField.unknown(reason="product catalog is empty - nothing to match against", confidence=0.1)

    query = " ".join(part for part in [brand, product_name, size] if part).strip().lower()
    candidates = _best_candidates(query, catalog)
    top = candidates[0]
    second_score = candidates[1].score if len(candidates) > 1 else 0.0

    if top.score < low_threshold:
        return ExtractedField.unknown(
            reason=(
                f"no catalog match found - closest candidate '{ProductCatalog.label_for(top.entry.product)}' "
                f"scored only {top.score:.0f}/100, below the {low_threshold:.0f} threshold"
            ),
            confidence=0.1,
        )

    if second_score >= low_threshold and (top.score - second_score) < ambiguous_margin:
        return ExtractedField.unknown(
            reason=(
                f"ambiguous match: '{ProductCatalog.label_for(top.entry.product)}' ({top.score:.0f}) and "
                f"'{ProductCatalog.label_for(candidates[1].entry.product)}' ({second_score:.0f}) are too close "
                "in score to confidently pick one"
            ),
            confidence=0.25,
        )

    # Scale the 0-100 fuzzy score into a 0-1 confidence; a score at/above the
    # high threshold is treated as a strong catalog match.
    span = max(100 - low_threshold, 1e-6)
    normalized = min(0.5 + (top.score - low_threshold) / span * 0.5, 0.97)
    if top.score >= high_threshold:
        normalized = max(normalized, 0.85)

    product = top.entry.product
    label = f"{product.id}: {ProductCatalog.label_for(product)}"
    return ExtractedField(
        value=label,
        confidence=round(normalized, 3),
        confidence_level=confidence_level_for(normalized, confidence_high_threshold, confidence_medium_threshold),
        reason=f"matched catalog entry '{ProductCatalog.label_for(product)}' with fuzzy score {top.score:.0f}/100",
    )
