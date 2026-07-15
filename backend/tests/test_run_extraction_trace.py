"""Integration-style test for vision/extractor.py::run_extraction - checks
that the AI Processing Trace correctly identifies which VisionClient
implementation produced an audit, end to end, through the real pipeline
(frame selection -> vision call -> validation -> grounding -> calibration).

Uses the MockVisionClient (no network) against a tiny synthetic JPEG so this
runs fast and offline, same as the rest of the suite.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from config import Settings
from sku.catalog import ProductCatalog
from vision.client import build_vision_client
from vision.extractor import run_extraction


def _write_test_image() -> Path:
    image = np.full((240, 320, 3), 200, dtype=np.uint8)
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(tmp.name, image)
    return Path(tmp.name)


class TestPipelineTraceIdentifiesActiveProvider:
    def test_trace_records_mock_provider_name_for_image_pipeline(self):
        image_path = _write_test_image()
        try:
            settings = Settings()
            vision_client = build_vision_client("mock")

            _audit, trace = run_extraction(
                media_path=image_path,
                media_type="image",
                account_id="00000000-0000-0000-0000-000000000000",
                media_reference="test.jpg",
                vision_client=vision_client,
                catalog=ProductCatalog([]),
                settings=settings,
            )

            assert trace["vision_provider"] == "Mock Vision"
        finally:
            image_path.unlink(missing_ok=True)

    def test_trace_reflects_whichever_provider_instance_was_passed_in(self):
        """The extractor must never hardcode a provider name - it has to read
        `vision_client.provider_name` from whatever was actually injected,
        so swapping providers via config alone changes what's shown in the
        trace, with zero changes to extractor.py."""
        image_path = _write_test_image()
        try:
            settings = Settings()

            class FakeCustomProvider:
                provider_name = "Custom Test Provider"

                def analyze_frame(self, image_bytes: bytes, frame_id: str, frame_context: str = "") -> str:
                    return "{}"

            _audit, trace = run_extraction(
                media_path=image_path,
                media_type="image",
                account_id="00000000-0000-0000-0000-000000000000",
                media_reference="test.jpg",
                vision_client=FakeCustomProvider(),  # type: ignore[arg-type]
                catalog=ProductCatalog([]),
                settings=settings,
            )

            assert trace["vision_provider"] == "Custom Test Provider"
        finally:
            image_path.unlink(missing_ok=True)
