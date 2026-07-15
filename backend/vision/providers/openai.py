"""Real vision inference via OpenAI's Chat Completions API.

Uses structured (`json_schema`, `strict: true`) outputs so the model is
contractually forced to return the `RawFrameObservation` shape that
`vision/validator.py` expects - this is the strongest guarantee available
short of writing a custom logits-constrained decoder, and it's why OpenAI is
the default/primary provider.
"""
from __future__ import annotations

import base64

from vision.client import VisionClient
from vision.prompts import FRAME_JSON_SCHEMA, SYSTEM_PROMPT, build_user_prompt


class OpenAIVisionClient(VisionClient):
    provider_name = "OpenAI Vision"

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI  # local import keeps the SDK optional for mock-only runs

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def analyze_frame(self, image_bytes: bytes, frame_id: str, frame_context: str = "") -> str:
        data_uri = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_user_prompt(frame_id, frame_context)},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
            response_format={"type": "json_schema", "json_schema": FRAME_JSON_SCHEMA},
        )
        return response.choices[0].message.content or "{}"
