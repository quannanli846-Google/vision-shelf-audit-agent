"""Unit tests for sku/matcher.py - the grounding layer.

Verifies the three required behaviors: confident match, ambiguous match
(no guess), and no match at all - each with the correct null/low-confidence
handling.
"""
from models.db_models import Product
from sku.catalog import ProductCatalog
from sku.matcher import match_product

from uuid import uuid4


def make_product(brand, name, size="750ml", aliases=None) -> Product:
    return Product(id=uuid4(), brand=brand, product_name=name, size=size, aliases=aliases or [])


def make_catalog() -> ProductCatalog:
    return ProductCatalog(
        [
            make_product("Tito's", "Handmade Vodka", "750ml", ["titos", "titos vodka"]),
            make_product("Grey Goose", "Vodka", "750ml", ["greygoose"]),
            make_product("Absolut", "Vodka", "750ml", ["absolut vodka"]),
            make_product("Jack Daniel's", "Old No. 7 Whiskey", "750ml", ["jack daniels", "jd"]),
        ]
    )


class TestConfidentMatch:
    def test_exact_brand_and_product_matches_with_high_confidence(self):
        catalog = make_catalog()
        result = match_product("Tito's", "Handmade Vodka", "750ml", catalog)

        assert result.value is not None
        assert "Tito's" in result.value
        assert result.confidence >= 0.75
        assert result.confidence_level.value == "high"
        assert "matched catalog entry" in result.reason

    def test_alias_matches(self):
        catalog = make_catalog()
        result = match_product("titos", None, None, catalog)

        assert result.value is not None
        assert "Tito's" in result.value

    def test_minor_typo_still_matches(self):
        catalog = make_catalog()
        result = match_product("Titos", "Handmade Vodca", "750ml", catalog)  # typo'd product name

        assert result.value is not None
        assert "Tito's" in result.value


class TestNoMatch:
    def test_unrelated_product_returns_null_not_a_guess(self):
        catalog = make_catalog()
        result = match_product("Some Random Brand", "Totally Unknown Product", "1L", catalog)

        assert result.value is None
        assert result.confidence_level.value == "low"
        assert "no catalog match found" in result.reason

    def test_empty_catalog_returns_null(self):
        catalog = ProductCatalog([])
        result = match_product("Tito's", "Handmade Vodka", "750ml", catalog)

        assert result.value is None
        assert "empty" in result.reason

    def test_no_brand_or_product_name_returns_null(self):
        catalog = make_catalog()
        result = match_product(None, None, "750ml", catalog)

        assert result.value is None
        assert "nothing to match" in result.reason


class TestAmbiguousMatch:
    def test_two_close_candidates_returns_null_rather_than_guessing(self):
        # Two near-identical "Vodka 750ml" entries with no distinguishing brand
        # signal should be flagged ambiguous, not silently resolved.
        catalog = ProductCatalog(
            [
                make_product("Absolut", "Vodka", "750ml"),
                make_product("Smirnoff", "Vodka", "750ml"),
            ]
        )
        result = match_product(None, "Vodka", "750ml", catalog, low_threshold=40.0, ambiguous_margin=50.0)

        assert result.value is None
        assert "ambiguous" in result.reason
        assert result.confidence_level.value == "low"


class TestNullValueInvariant:
    def test_null_match_never_reports_high_or_medium_confidence(self):
        catalog = make_catalog()
        for brand, name in [(None, None), ("Unrelated", "Thing"), ("Absolut", "Vodka")]:
            result = match_product(brand, name, None, catalog, low_threshold=95.0)  # force everything below threshold
            if result.value is None:
                assert result.confidence_level.value == "low"
