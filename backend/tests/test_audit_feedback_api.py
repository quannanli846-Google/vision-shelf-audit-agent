"""API-level tests for the human review loop: POST/GET
/api/audits/{id}/feedback.

Uses FastAPI's TestClient with a dependency override pointing at a fresh
`InMemoryAuditRepository` per test, so these never touch Supabase, a real
vision provider, or module-level lru_cache state shared with other tests.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database.dependencies import get_repository
from database.repository import InMemoryAuditRepository
from main import app


@pytest.fixture()
def repository() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture()
def client(repository: InMemoryAuditRepository) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_repository, None)


@pytest.fixture()
def audit_id(repository: InMemoryAuditRepository) -> str:
    account = repository.list_accounts()[0]
    audit = repository.create_audit(account.id, media_url="https://example.com/shelf.jpg", media_type="image")
    return str(audit.id)


class TestCreateFeedback:
    def test_confirm_action_persists_without_a_corrected_value(self, client: TestClient, audit_id: str):
        response = client.post(
            f"/api/audits/{audit_id}/feedback",
            json={"field": "products_observed[0].brand", "review_action": "confirm", "ai_value": "Tito's", "ai_confidence": 0.86},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["review_action"] == "confirm"
        assert body["ai_value"] == "Tito's"
        assert body["corrected_value"] is None
        assert body["audit_id"] == audit_id

    def test_correct_action_persists_the_corrected_value(self, client: TestClient, audit_id: str):
        response = client.post(
            f"/api/audits/{audit_id}/feedback",
            json={
                "field": "products_observed[1].brand",
                "review_action": "correct",
                "ai_value": None,
                "ai_confidence": 0.32,
                "corrected_value": "Jack Daniel's Old No.7",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["review_action"] == "correct"
        assert body["corrected_value"] == "Jack Daniel's Old No.7"

    def test_reject_action_is_accepted(self, client: TestClient, audit_id: str):
        response = client.post(
            f"/api/audits/{audit_id}/feedback",
            json={"field": "out_of_stock_signals[0].likely_product", "review_action": "reject"},
        )
        assert response.status_code == 201
        assert response.json()["review_action"] == "reject"

    def test_invalid_review_action_is_rejected(self, client: TestClient, audit_id: str):
        response = client.post(
            f"/api/audits/{audit_id}/feedback",
            json={"field": "products_observed[0].brand", "review_action": "maybe"},
        )
        assert response.status_code == 422

    def test_feedback_for_unknown_audit_returns_404(self, client: TestClient):
        response = client.post(
            "/api/audits/00000000-0000-0000-0000-000000000000/feedback",
            json={"field": "brand", "review_action": "confirm"},
        )
        assert response.status_code == 404

    def test_feedback_never_mutates_the_audit_record(self, client: TestClient, audit_id: str, repository: InMemoryAuditRepository):
        before = repository.get_audit(__import__("uuid").UUID(audit_id))
        client.post(f"/api/audits/{audit_id}/feedback", json={"field": "brand", "review_action": "reject"})
        after = repository.get_audit(__import__("uuid").UUID(audit_id))
        assert before == after


class TestListFeedback:
    def test_lists_feedback_newest_first(self, client: TestClient, audit_id: str):
        client.post(f"/api/audits/{audit_id}/feedback", json={"field": "brand", "review_action": "confirm"})
        client.post(f"/api/audits/{audit_id}/feedback", json={"field": "size", "review_action": "reject"})

        response = client.get(f"/api/audits/{audit_id}/feedback")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["field"] == "size"  # most recent first

    def test_empty_when_no_feedback_submitted_yet(self, client: TestClient, audit_id: str):
        response = client.get(f"/api/audits/{audit_id}/feedback")
        assert response.status_code == 200
        assert response.json() == []

    def test_unknown_audit_returns_404(self, client: TestClient):
        response = client.get("/api/audits/00000000-0000-0000-0000-000000000000/feedback")
        assert response.status_code == 404
