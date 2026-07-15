"""Deterministic stand-in used when no real vision provider is configured.

Cycles through a small set of realistic, clearly-labeled fixture responses so
the entire pipeline (validation, grounding, confidence calibration,
multi-frame merge, persistence, UI) can be exercised end-to-end without any
external API access. Every fixture's "notes" field is prefixed with
"[MOCK VISION CLIENT]" so it's never mistaken for a genuine model result.
"""
from __future__ import annotations

import json

from vision.client import VisionClient


class MockVisionClient(VisionClient):
    provider_name = "Mock Vision"

    def __init__(self):
        self._call_count = 0

    def analyze_frame(self, image_bytes: bytes, frame_id: str, frame_context: str = "") -> str:
        fixture = _MOCK_FIXTURES[self._call_count % len(_MOCK_FIXTURES)]
        self._call_count += 1
        return json.dumps(fixture)


_MOCK_FIXTURES: list[dict] = [
    {
        "products": [
            {
                "brand": {"value": "Tito's", "confidence": 0.9, "reason": "brand label clearly visible on multiple bottle facings"},
                "product_name": {"value": "Handmade Vodka", "confidence": 0.88, "reason": "product text legible on label"},
                "size": {"value": "750ml", "confidence": 0.7, "reason": "bottle silhouette consistent with 750ml, size text partially visible"},
                "facings": {"value": 4, "confidence": 0.8, "reason": "4 identical bottles counted left to right"},
                "shelf_level": {"value": "eye-level", "confidence": 0.75, "reason": "positioned at approximate eye height in frame"},
            },
            {
                "brand": {"value": "Jack Daniel's", "confidence": 0.82, "reason": "distinctive black label visible"},
                "product_name": {"value": "Old No. 7 Whiskey", "confidence": 0.78, "reason": "label text legible"},
                "size": {"value": "750ml", "confidence": 0.6, "reason": "typical bottle size, size text not clearly legible"},
                "facings": {"value": 3, "confidence": 0.7, "reason": "3 bottles counted"},
                "shelf_level": {"value": "top", "confidence": 0.65, "reason": "positioned on uppermost visible shelf"},
            },
            {
                "brand": {"value": None, "confidence": 0.2, "reason": "label obscured by glare, brand not legible"},
                "product_name": {"value": None, "confidence": 0.15, "reason": "product text not visible"},
                "size": {"value": None, "confidence": 0.1, "reason": "size text not visible"},
                "facings": {"value": 2, "confidence": 0.4, "reason": "two bottle silhouettes visible but unidentifiable"},
                "shelf_level": {"value": "bottom", "confidence": 0.5, "reason": "lowest shelf in frame"},
            },
        ],
        "out_of_stock_signals": [
            {
                "location": {"value": "middle shelf, right section", "confidence": 0.6, "reason": "visible gap between product groups with exposed shelf liner"},
                "likely_product": {"value": None, "confidence": 0.2, "reason": "no signage or tag indicates what should be stocked there"},
            }
        ],
        "shelf_positions": [
            {
                "level": {"value": "top", "confidence": 0.7, "reason": "whiskey section occupies top shelf"},
                "description": {"value": "whiskey and bourbon selection", "confidence": 0.65, "reason": "brand labels consistent with whiskey category"},
            },
            {
                "level": {"value": "eye-level", "confidence": 0.75, "reason": "vodka section at eye level"},
                "description": {"value": "vodka selection", "confidence": 0.7, "reason": "Tito's facings dominate this level"},
            },
        ],
        "promotions": [
            {
                "promo_type": {"value": "shelf-talker", "confidence": 0.55, "reason": "small yellow sign clipped to shelf edge"},
                "text_detected": {"value": None, "confidence": 0.2, "reason": "text on sign too small/blurry to read"},
                "associated_product": {"value": "Tito's Handmade Vodka", "confidence": 0.4, "reason": "sign positioned directly below vodka facings"},
            }
        ],
        "pricing_reads": [
            {
                "product": {"value": "Tito's Handmade Vodka", "confidence": 0.5, "reason": "price tag visible below facings but partially cropped"},
                "price": {"value": None, "confidence": 0.2, "reason": "digits not legible at this resolution"},
            }
        ],
        "compliance_flags": [],
        "notes": "[MOCK VISION CLIENT] Synthetic analysis - no real model inference was performed. Representative shelf with vodka and whiskey sections; one product cluster near the bottom shelf could not be identified confidently.",
    },
    {
        "products": [
            {
                "brand": {"value": "Corona", "confidence": 0.85, "reason": "distinctive label and bottle shape recognizable"},
                "product_name": {"value": "Extra", "confidence": 0.8, "reason": "label text visible"},
                "size": {"value": "12pk", "confidence": 0.72, "reason": "carton packaging consistent with 12-pack"},
                "facings": {"value": 5, "confidence": 0.78, "reason": "5 cartons counted across shelf"},
                "shelf_level": {"value": "middle", "confidence": 0.6, "reason": "centered vertically in frame"},
            },
            {
                "brand": {"value": "Heineken", "confidence": 0.7, "reason": "green packaging and red star logo visible"},
                "product_name": {"value": "Lager", "confidence": 0.6, "reason": "standard lager labeling"},
                "size": {"value": "12pk", "confidence": 0.55, "reason": "carton size approximate, partially occluded"},
                "facings": {"value": 2, "confidence": 0.55, "reason": "2 cartons visible, one partially hidden"},
                "shelf_level": {"value": "middle", "confidence": 0.5, "reason": "same shelf as Corona"},
            },
        ],
        "out_of_stock_signals": [
            {
                "location": {"value": "left section of middle shelf", "confidence": 0.75, "reason": "large empty gap with visible shelf tag but no product"},
                "likely_product": {"value": "Bud Light", "confidence": 0.45, "reason": "adjacent shelf tag reads partial text consistent with Bud Light branding"},
            }
        ],
        "shelf_positions": [
            {
                "level": {"value": "middle", "confidence": 0.65, "reason": "beer section occupies the middle shelf band"},
                "description": {"value": "beer 12-pack selection", "confidence": 0.6, "reason": "carton packaging typical of beer 12-packs"},
            }
        ],
        "promotions": [
            {
                "promo_type": {"value": "end-cap sign", "confidence": 0.7, "reason": "large printed sign visible above the beer section"},
                "text_detected": {"value": "SUMMER SALE", "confidence": 0.6, "reason": "bold text partially legible on sign"},
                "associated_product": {"value": None, "confidence": 0.3, "reason": "sign does not clearly reference one specific product"},
            }
        ],
        "pricing_reads": [
            {
                "product": {"value": "Corona Extra", "confidence": 0.55, "reason": "price tag visible beneath facings"},
                "price": {"value": "$14.99", "confidence": 0.5, "reason": "digits legible but at a shallow viewing angle"},
            }
        ],
        "compliance_flags": [
            {
                "issue_type": {"value": "missing age-restriction signage", "confidence": 0.35, "reason": "no visible age-restriction placard in an alcohol section, but full shelf extent is not visible in frame"},
                "description": {"value": "Required signage may simply be out of frame rather than absent", "confidence": 0.3, "reason": "cannot confirm absence vs. out-of-frame"},
            }
        ],
        "notes": "[MOCK VISION CLIENT] Synthetic analysis - no real model inference was performed. Beer section shows a likely out-of-stock gap and active summer promotion signage.",
    },
]
