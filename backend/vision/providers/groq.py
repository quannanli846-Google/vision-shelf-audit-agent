"""Vision inference via Groq's OpenAI-compatible chat completions API.

Groq's vision-capable models (Llama 4 Scout/Maverick) don't offer the same
strict `json_schema` decode-time enforcement OpenAI does - only a looser
`json_object` mode - so this provider leans harder on an explicit schema
reminder in the prompt (`JSON_MODE_SCHEMA_HINT`). That's a real accuracy
trade-off versus the OpenAI provider, not a bug: `vision/validator.py`
downstream is exactly what makes this safe either way, by discarding any
frame whose output doesn't match the trusted shape rather than guessing.
"""
from __future__ import annotations

import base64

from vision.client import VisionClient
from vision.prompts import SYSTEM_PROMPT, JSON_MODE_SCHEMA_HINT, build_user_prompt

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqVisionClient(VisionClient):
    provider_name = "Groq Vision"

    def __init__(self, api_key: str, model: str = "meta-llama/llama-4-scout-17b-16e-instruct"):
        from openai import OpenAI  # Groq's API is OpenAI-SDK compatible via base_url

        self._client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        self._model = model

    def analyze_frame(self, image_bytes: bytes, frame_id: str, frame_context: str = "") -> str:
        data_uri = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + JSON_MODE_SCHEMA_HINT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_user_prompt(frame_id, frame_context)},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"
