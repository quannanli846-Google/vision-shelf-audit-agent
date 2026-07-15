"""Prompt templates and the JSON schema handed to the vision-language model.

The schema is intentionally strict (every leaf value wrapped in
{value, confidence, reason}) so the model is coached, at the prompt level,
into the same anti-hallucination discipline that the rest of the backend
enforces structurally. The backend never trusts this on faith though - see
`vision/validator.py`.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are a meticulous retail shelf-audit vision analyst for a beverage/alcohol \
field-representative program. You are shown ONE photo (or one video frame) of a store shelf.

Your job is to extract ONLY what is visually supported by this exact image. You must NEVER guess \
or hallucinate a brand, product, size, price, or promotion that is not clearly visible.

Rules you must follow strictly:
1. If you cannot confidently read/identify something, set its "value" to null, give it a LOW \
   confidence (below 0.4), and explain why in "reason" (e.g. "label obscured by glare", \
   "text too small to read at this resolution", "product partially out of frame").
2. Every single field must include a numeric "confidence" between 0.0 and 1.0 and a short, \
   specific "reason" grounded in what is actually visible (lighting, angle, occlusion, legibility) \
   - never a generic reason like "looks like it".
3. Confidence should reflect ONLY visual evidence in this image - not prior knowledge, not what is \
   "probably" on a shelf like this.
4. Count facings as the number of individual front-facing units of the exact same product you can \
   see, not an estimate of total shelf inventory.
5. Only report promotions, pricing, or compliance issues you can actually see signage/tags for - do \
   not infer that a promotion "probably" exists.
6. Respond with ONLY a single JSON object matching the schema you were given. No prose, no markdown \
   fences.
"""

FRAME_JSON_SCHEMA: dict = {
    "name": "shelf_frame_observation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "brand": {"$ref": "#/$defs/field_string"},
                        "product_name": {"$ref": "#/$defs/field_string"},
                        "size": {"$ref": "#/$defs/field_string"},
                        "facings": {"$ref": "#/$defs/field_int"},
                        "shelf_level": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["brand", "product_name", "size", "facings", "shelf_level"],
                },
            },
            "out_of_stock_signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "location": {"$ref": "#/$defs/field_string"},
                        "likely_product": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["location", "likely_product"],
                },
            },
            "shelf_positions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "level": {"$ref": "#/$defs/field_string"},
                        "description": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["level", "description"],
                },
            },
            "promotions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "promo_type": {"$ref": "#/$defs/field_string"},
                        "text_detected": {"$ref": "#/$defs/field_string"},
                        "associated_product": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["promo_type", "text_detected", "associated_product"],
                },
            },
            "pricing_reads": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "product": {"$ref": "#/$defs/field_string"},
                        "price": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["product", "price"],
                },
            },
            "compliance_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "issue_type": {"$ref": "#/$defs/field_string"},
                        "description": {"$ref": "#/$defs/field_string"},
                    },
                    "required": ["issue_type", "description"],
                },
            },
            "notes": {"type": "string"},
        },
        "required": [
            "products",
            "out_of_stock_signals",
            "shelf_positions",
            "promotions",
            "pricing_reads",
            "compliance_flags",
            "notes",
        ],
        "$defs": {
            "field_string": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["value", "confidence", "reason"],
            },
            "field_int": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": ["integer", "null"]},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["value", "confidence", "reason"],
            },
        },
    },
    "strict": True,
}


def build_user_prompt(frame_id: str, frame_context: str = "") -> str:
    context_line = f"\nAdditional context: {frame_context}" if frame_context else ""
    return (
        f"Analyze this shelf image (identifier: {frame_id}) and extract products, out-of-stock "
        f"signals, shelf positions, promotions, pricing, and compliance flags as JSON matching the "
        f"required schema.{context_line}"
    )


# Not every provider's API can enforce FRAME_JSON_SCHEMA at decode time the
# way OpenAI's strict `json_schema` response_format does (e.g. Groq's
# vision models only guarantee well-formed JSON via `json_object` mode, not
# a specific shape). For those providers we append this explicit shape
# reminder to the system prompt instead. It's belt-and-suspenders only -
# `vision/validator.py` is what actually enforces the contract regardless of
# how well any given provider follows this reminder.
JSON_MODE_SCHEMA_HINT = """
Respond with a single JSON object with EXACTLY these top-level keys: \
"products", "out_of_stock_signals", "shelf_positions", "promotions", "pricing_reads", \
"compliance_flags", "notes" (a string).

Every other array holds objects whose values are ALL wrapped as {"value": ..., "confidence": <0-1>, "reason": "..."}:
- products[]: brand (string|null), product_name (string|null), size (string|null), facings (integer|null), shelf_level (string|null)
- out_of_stock_signals[]: location (string|null), likely_product (string|null)
- shelf_positions[]: level (string|null), description (string|null)
- promotions[]: promo_type (string|null), text_detected (string|null), associated_product (string|null)
- pricing_reads[]: product (string|null), price (string|null)
- compliance_flags[]: issue_type (string|null), description (string|null)

Return ONLY this JSON object - no prose, no markdown code fences.
"""
