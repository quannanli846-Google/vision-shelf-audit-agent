"""API-level tests for the developer/demo "Vision Provider" switch:
GET/POST /api/settings/vision-provider.

Uses dependency overrides for both `get_settings` and
`get_vision_provider_state` so each test gets a fresh, isolated state - never
sharing the module-level `@lru_cache`'d singletons with other test files or
between tests in this file.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import Settings, get_settings
from main import app
from services.vision_provider_state import VisionProviderState, get_vision_provider_state


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


@pytest.fixture()
def state() -> VisionProviderState:
    return VisionProviderState(default_provider="mock")


def _client(settings: Settings, state: VisionProviderState) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_vision_provider_state] = lambda: state
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_vision_provider_state, None)


class TestGetVisionProvider:
    def test_defaults_to_mock_when_no_api_keys_configured(self, state: VisionProviderState):
        client = _client(_settings(), state)

        response = client.get("/api/settings/vision-provider")

        assert response.status_code == 200
        body = response.json()
        assert body["active_provider"] == "mock"
        assert body["label"] == "Mock Vision"
        assert body["is_dev_override"] is False
        assert body["default_provider"] == "mock"

    def test_lists_exactly_the_three_known_providers_with_availability(self, state: VisionProviderState):
        client = _client(_settings(openai_api_key="sk-test"), state)

        response = client.get("/api/settings/vision-provider")

        options = {opt["provider"]: opt for opt in response.json()["options"]}
        assert set(options) == {"mock", "openai", "groq"}
        assert options["mock"]["available"] is True
        assert options["openai"]["available"] is True
        assert options["groq"]["available"] is False
        assert "GROQ_API_KEY" in options["groq"]["unavailable_reason"]


class TestSetVisionProvider:
    def test_switching_to_mock_always_succeeds(self, state: VisionProviderState):
        client = _client(_settings(), state)

        response = client.post("/api/settings/vision-provider", json={"provider": "mock"})

        assert response.status_code == 200
        body = response.json()
        assert body["active_provider"] == "mock"
        assert body["is_dev_override"] is True  # explicitly chosen, even though it matches the default

    def test_switching_to_openai_succeeds_when_key_is_configured(self, state: VisionProviderState):
        client = _client(_settings(openai_api_key="sk-test"), state)

        response = client.post("/api/settings/vision-provider", json={"provider": "openai"})

        assert response.status_code == 200
        body = response.json()
        assert body["active_provider"] == "openai"
        assert body["label"] == "OpenAI Vision"
        assert body["is_dev_override"] is True

    def test_switching_to_openai_without_a_key_is_rejected_with_a_clear_reason(self, state: VisionProviderState):
        client = _client(_settings(), state)

        response = client.post("/api/settings/vision-provider", json={"provider": "openai"})

        assert response.status_code == 400
        assert "OPENAI_API_KEY" in response.json()["detail"]
        # A rejected switch must never silently change the active provider.
        assert state.active_provider == "mock"
        assert state.is_dev_override is False

    def test_switching_to_groq_without_a_key_is_rejected(self, state: VisionProviderState):
        client = _client(_settings(), state)

        response = client.post("/api/settings/vision-provider", json={"provider": "groq"})

        assert response.status_code == 400
        assert "GROQ_API_KEY" in response.json()["detail"]

    def test_unknown_provider_name_is_rejected_by_schema_validation(self, state: VisionProviderState):
        client = _client(_settings(), state)

        response = client.post("/api/settings/vision-provider", json={"provider": "anthropic"})

        assert response.status_code == 422

    def test_switch_is_reflected_by_a_subsequent_get(self, state: VisionProviderState):
        client = _client(_settings(openai_api_key="sk-test"), state)

        client.post("/api/settings/vision-provider", json={"provider": "openai"})
        response = client.get("/api/settings/vision-provider")

        assert response.json()["active_provider"] == "openai"


class TestHealthEndpointReflectsActiveProvider:
    def test_health_reports_dev_override_once_switched(self, state: VisionProviderState):
        client = _client(_settings(openai_api_key="sk-test"), state)

        client.post("/api/settings/vision-provider", json={"provider": "openai"})
        response = client.get("/api/health")

        body = response.json()
        assert body["vision_provider"] == "openai"
        assert body["vision_provider_is_dev_override"] is True
