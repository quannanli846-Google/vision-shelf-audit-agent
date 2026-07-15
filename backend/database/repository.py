"""Repository layer: the ONLY code in the application allowed to talk to the
database. API routes and the vision pipeline depend on the `AuditRepository`
interface, never on Supabase directly - this keeps every layer independently
testable (swap in `InMemoryAuditRepository` for unit/integration tests) and
means switching persistence backends never touches business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from models.db_models import Account, Audit, AuditFeedback, AuditFeedbackCreate, AuditStatus, Product


class AuditRepository(ABC):
    # --- accounts ---
    @abstractmethod
    def list_accounts(self) -> list[Account]: ...

    @abstractmethod
    def get_account(self, account_id: UUID) -> Optional[Account]: ...

    # --- products (SKU catalog) ---
    @abstractmethod
    def list_products(self) -> list[Product]: ...

    # --- audits ---
    @abstractmethod
    def create_audit(self, account_id: UUID, media_url: str, media_type: str) -> Audit: ...

    @abstractmethod
    def get_audit(self, audit_id: UUID) -> Optional[Audit]: ...

    @abstractmethod
    def list_audits(self, account_id: Optional[UUID] = None) -> list[Audit]: ...

    @abstractmethod
    def update_audit_status(
        self,
        audit_id: UUID,
        status: AuditStatus,
        status_message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Audit: ...

    @abstractmethod
    def complete_audit(self, audit_id: UUID, audit_json: dict[str, Any]) -> Audit: ...

    # --- human review feedback ---
    @abstractmethod
    def create_feedback(self, audit_id: UUID, feedback: AuditFeedbackCreate) -> AuditFeedback: ...

    @abstractmethod
    def list_feedback(self, audit_id: UUID) -> list[AuditFeedback]: ...


class SupabaseAuditRepository(AuditRepository):
    """Production repository backed by Supabase Postgres (via supabase-py)."""

    def __init__(self, client):
        self._client = client

    def list_accounts(self) -> list[Account]:
        res = self._client.table("accounts").select("*").order("store_name").execute()
        return [Account.model_validate(row) for row in res.data]

    def get_account(self, account_id: UUID) -> Optional[Account]:
        res = self._client.table("accounts").select("*").eq("id", str(account_id)).limit(1).execute()
        return Account.model_validate(res.data[0]) if res.data else None

    def list_products(self) -> list[Product]:
        res = self._client.table("products").select("*").order("brand").execute()
        return [Product.model_validate(row) for row in res.data]

    def create_audit(self, account_id: UUID, media_url: str, media_type: str) -> Audit:
        res = (
            self._client.table("audits")
            .insert(
                {
                    "account_id": str(account_id),
                    "media_url": media_url,
                    "media_type": media_type,
                    "status": "uploaded",
                }
            )
            .execute()
        )
        return Audit.model_validate(res.data[0])

    def get_audit(self, audit_id: UUID) -> Optional[Audit]:
        res = self._client.table("audits").select("*").eq("id", str(audit_id)).limit(1).execute()
        return Audit.model_validate(res.data[0]) if res.data else None

    def list_audits(self, account_id: Optional[UUID] = None) -> list[Audit]:
        query = self._client.table("audits").select("*").order("created_at", desc=True)
        if account_id is not None:
            query = query.eq("account_id", str(account_id))
        res = query.execute()
        return [Audit.model_validate(row) for row in res.data]

    def update_audit_status(
        self,
        audit_id: UUID,
        status: AuditStatus,
        status_message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Audit:
        payload: dict[str, Any] = {"status": status}
        if status_message is not None:
            payload["status_message"] = status_message
        if error_message is not None:
            payload["error_message"] = error_message
        res = self._client.table("audits").update(payload).eq("id", str(audit_id)).execute()
        return Audit.model_validate(res.data[0])

    def complete_audit(self, audit_id: UUID, audit_json: dict[str, Any]) -> Audit:
        res = (
            self._client.table("audits")
            .update({"status": "completed", "audit_json": audit_json, "status_message": "audit complete"})
            .eq("id", str(audit_id))
            .execute()
        )
        return Audit.model_validate(res.data[0])

    def create_feedback(self, audit_id: UUID, feedback: AuditFeedbackCreate) -> AuditFeedback:
        res = (
            self._client.table("audit_feedback")
            .insert(
                {
                    "audit_id": str(audit_id),
                    "field": feedback.field,
                    "review_action": feedback.review_action,
                    "ai_value": feedback.ai_value,
                    "ai_confidence": feedback.ai_confidence,
                    "corrected_value": feedback.corrected_value,
                }
            )
            .execute()
        )
        return AuditFeedback.model_validate(res.data[0])

    def list_feedback(self, audit_id: UUID) -> list[AuditFeedback]:
        res = (
            self._client.table("audit_feedback")
            .select("*")
            .eq("audit_id", str(audit_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [AuditFeedback.model_validate(row) for row in res.data]


class InMemoryAuditRepository(AuditRepository):
    """Dependency-free repository used for local development without a
    Supabase project and for fast, isolated unit/integration tests.

    Seeded with data that mirrors `migrations/001_init.sql` so the app
    behaves the same way regardless of which backend is active.
    """

    def __init__(self):
        self._accounts: dict[UUID, Account] = {}
        self._products: dict[UUID, Product] = {}
        self._audits: dict[UUID, Audit] = {}
        self._feedback: dict[UUID, list[AuditFeedback]] = {}
        self._seed()

    def _seed(self) -> None:
        now = datetime.now(timezone.utc)
        for store_name in ["Riverside Liquor & Wine", "Downtown Market #142", "Sunset Beverage Depot"]:
            acc = Account(id=uuid4(), store_name=store_name, created_at=now)
            self._accounts[acc.id] = acc

        seed_products = [
            ("Tito's", "Handmade Vodka", "750ml", ["titos", "titos vodka", "handmade vodka"]),
            ("Tito's", "Handmade Vodka", "1.75L", ["titos 1.75", "titos handle"]),
            ("Grey Goose", "Vodka", "750ml", ["greygoose", "grey goose vodka"]),
            ("Absolut", "Vodka", "750ml", ["absolut vodka"]),
            ("Smirnoff", "No. 21 Vodka", "750ml", ["smirnoff vodka", "smirnoff no 21"]),
            ("Jack Daniel's", "Old No. 7 Whiskey", "750ml", ["jack daniels", "jd", "old no 7"]),
            ("Jameson", "Irish Whiskey", "750ml", ["jameson whiskey", "jameson irish"]),
            ("Jim Beam", "Kentucky Bourbon", "750ml", ["jim beam bourbon"]),
            ("Bacardi", "Superior Rum", "750ml", ["bacardi superior", "bacardi white"]),
            ("Captain Morgan", "Original Spiced Rum", "750ml", ["captain morgan spiced"]),
            ("Patron", "Silver Tequila", "750ml", ["patron silver", "patron tequila"]),
            ("Casamigos", "Blanco Tequila", "750ml", ["casamigos blanco"]),
            ("Corona", "Extra", "12pk", ["corona extra 12 pack", "corona beer"]),
            ("Bud Light", "Lager", "12pk", ["budlight", "bud light beer"]),
            ("Heineken", "Lager", "12pk", ["heineken beer", "heineken lager"]),
            ("White Claw", "Hard Seltzer Variety", "12pk", ["white claw variety pack", "whiteclaw"]),
            ("Smirnoff Ice", "Malt Beverage", "6pk", ["smirnoff ice 6 pack"]),
            ("Coca-Cola", "Classic", "12pk cans", ["coke", "coca cola classic"]),
            ("Pepsi", "Cola", "12pk cans", ["pepsi cola"]),
            ("Topo Chico", "Mineral Water", "12pk", ["topo chico sparkling water"]),
        ]
        for brand, name, size, aliases in seed_products:
            p = Product(id=uuid4(), brand=brand, product_name=name, size=size, aliases=aliases, created_at=now)
            self._products[p.id] = p

    def list_accounts(self) -> list[Account]:
        return sorted(self._accounts.values(), key=lambda a: a.store_name)

    def get_account(self, account_id: UUID) -> Optional[Account]:
        return self._accounts.get(account_id)

    def list_products(self) -> list[Product]:
        return sorted(self._products.values(), key=lambda p: p.brand)

    def create_audit(self, account_id: UUID, media_url: str, media_type: str) -> Audit:
        now = datetime.now(timezone.utc)
        audit = Audit(
            id=uuid4(),
            account_id=account_id,
            media_url=media_url,
            media_type=media_type,  # type: ignore[arg-type]
            status="uploaded",
            status_message="media uploaded, awaiting processing",
            audit_json=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        self._audits[audit.id] = audit
        return audit

    def get_audit(self, audit_id: UUID) -> Optional[Audit]:
        return self._audits.get(audit_id)

    def list_audits(self, account_id: Optional[UUID] = None) -> list[Audit]:
        items = list(self._audits.values())
        if account_id is not None:
            items = [a for a in items if a.account_id == account_id]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def update_audit_status(
        self,
        audit_id: UUID,
        status: AuditStatus,
        status_message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Audit:
        audit = self._audits[audit_id]
        updated = audit.model_copy(
            update={
                "status": status,
                "status_message": status_message if status_message is not None else audit.status_message,
                "error_message": error_message if error_message is not None else audit.error_message,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._audits[audit_id] = updated
        return updated

    def complete_audit(self, audit_id: UUID, audit_json: dict[str, Any]) -> Audit:
        audit = self._audits[audit_id]
        updated = audit.model_copy(
            update={
                "status": "completed",
                "status_message": "audit complete",
                "audit_json": audit_json,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._audits[audit_id] = updated
        return updated

    def create_feedback(self, audit_id: UUID, feedback: AuditFeedbackCreate) -> AuditFeedback:
        record = AuditFeedback(
            id=uuid4(),
            audit_id=audit_id,
            field=feedback.field,
            review_action=feedback.review_action,
            ai_value=feedback.ai_value,
            ai_confidence=feedback.ai_confidence,
            corrected_value=feedback.corrected_value,
            created_at=datetime.now(timezone.utc),
        )
        self._feedback.setdefault(audit_id, []).append(record)
        return record

    def list_feedback(self, audit_id: UUID) -> list[AuditFeedback]:
        return sorted(self._feedback.get(audit_id, []), key=lambda f: f.created_at, reverse=True)
