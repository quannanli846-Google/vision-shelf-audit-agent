"""In-memory, pre-indexed view of the SKU reference catalog used for grounding.

Deliberately decoupled from the database layer - `ProductCatalog` is built
from a plain list of `Product` objects, so `sku/matcher.py` and this module
can be unit-tested with a handful of hand-written products and never need a
real database connection.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.db_models import Product


@dataclass
class CatalogEntry:
    product: Product
    search_strings: list[str] = field(default_factory=list)


class ProductCatalog:
    def __init__(self, products: list[Product]):
        self._entries = [self._build_entry(p) for p in products]

    @staticmethod
    def _build_entry(product: Product) -> CatalogEntry:
        base = f"{product.brand} {product.product_name}".strip()
        strings = {base.lower()}
        if product.size:
            strings.add(f"{base} {product.size}".lower())
        for alias in product.aliases:
            strings.add(alias.lower())
        return CatalogEntry(product=product, search_strings=sorted(strings))

    @property
    def entries(self) -> list[CatalogEntry]:
        return self._entries

    def is_empty(self) -> bool:
        return not self._entries

    @staticmethod
    def label_for(product: Product) -> str:
        parts = [product.brand, product.product_name]
        if product.size:
            parts.append(f"({product.size})")
        return " ".join(parts)
