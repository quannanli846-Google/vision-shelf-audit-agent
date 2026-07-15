"""Tests for the vision provider factory (`vision/client.py`).

These only check *selection/wiring* - which class gets instantiated for a
given provider name/config, and that misconfiguration fails loudly - never
make a real network call, so they run offline in CI same as everything else.
"""
from __future__ import annotations

import pytest

from vision.client import build_vision_client
from vision.providers.groq import GROQ_BASE_URL, GroqVisionClient
from vision.providers.mock import MockVisionClient
from vision.providers.openai import OpenAIVisionClient


class TestMockProvider:
    def test_mock_provider_name_returns_mock_client(self):
        client = build_vision_client("mock")
        assert isinstance(client, MockVisionClient)

    def test_unknown_provider_name_falls_back_to_mock(self):
        client = build_vision_client("something-unrecognized")
        assert isinstance(client, MockVisionClient)


class TestOpenAIProvider:
    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            build_vision_client("openai", openai_api_key="")

    def test_with_api_key_builds_openai_client(self):
        client = build_vision_client("openai", openai_api_key="sk-test-key", openai_model="gpt-4o")
        assert isinstance(client, OpenAIVisionClient)


class TestGroqProvider:
    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            build_vision_client("groq", groq_api_key="")

    def test_with_api_key_builds_groq_client_pointed_at_groq_base_url(self):
        client = build_vision_client("groq", groq_api_key="gsk-test-key")
        assert isinstance(client, GroqVisionClient)
        # Groq is only reachable through this override - if it silently fell
        # back to OpenAI's default base_url, calls would 401 against the
        # wrong provider instead of Groq.
        assert str(client._client.base_url).rstrip("/") == GROQ_BASE_URL


class TestVisionClientInterfaceIsProviderAgnostic:
    def test_all_providers_expose_the_same_analyze_frame_signature(self):
        import inspect

        from vision.client import VisionClient

        mock_sig = inspect.signature(MockVisionClient.analyze_frame)
        openai_sig = inspect.signature(OpenAIVisionClient.analyze_frame)
        groq_sig = inspect.signature(GroqVisionClient.analyze_frame)
        assert mock_sig == openai_sig == groq_sig
        assert issubclass(MockVisionClient, VisionClient)
        assert issubclass(OpenAIVisionClient, VisionClient)
        assert issubclass(GroqVisionClient, VisionClient)

    def test_each_provider_exposes_a_distinct_human_readable_name(self):
        """The AI Processing Trace surfaces `provider_name` verbatim so a
        reviewer can see which replaceable perception backend produced a
        given audit - every provider must set a real, distinct label."""
        mock_client = build_vision_client("mock")
        openai_client = build_vision_client("openai", openai_api_key="sk-test-key")
        groq_client = build_vision_client("groq", groq_api_key="gsk-test-key")

        assert mock_client.provider_name == "Mock Vision"
        assert openai_client.provider_name == "OpenAI Vision"
        assert groq_client.provider_name == "Groq Vision"
        names = {mock_client.provider_name, openai_client.provider_name, groq_client.provider_name}
        assert len(names) == 3, "every provider must have a distinct name"
