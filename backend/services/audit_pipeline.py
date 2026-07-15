"""Background pipeline runner: the glue between the API layer and the vision
pipeline. Deliberately NOT inside `api/audits.py` - no OpenAI/vision calls
ever happen inside a route handler, so the pipeline can be invoked and
tested independently of FastAPI/HTTP entirely.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from config import Settings
from database.repository import AuditRepository
from database.storage import MediaStorage
from sku.catalog import ProductCatalog
from vision.client import build_vision_client
from vision.extractor import run_extraction

logger = logging.getLogger("shelf_audit.pipeline")


def process_audit(
    audit_id: UUID,
    repository: AuditRepository,
    storage: MediaStorage,
    settings: Settings,
    resolved_vision_provider: str | None = None,
) -> None:
    """Runs the full pipeline for one audit and persists the result.

    `resolved_vision_provider` is which provider name to build the
    `VisionClient` with for *this* audit - callers pass
    `VisionProviderState.active_provider` (see `services/vision_provider_state.py`)
    so the developer "Vision Provider" switch takes effect immediately,
    without this module ever knowing that switch exists. Defaults to the
    environment-configured provider (`settings.resolved_vision_provider()`)
    when omitted, so nothing breaks for any caller that predates the switch.

    Never raises - any failure is caught and recorded on the audit row as
    `status=failed` with an `error_message`, so a bad upload/model failure
    can never leave an audit stuck in `processing` forever.
    """
    if resolved_vision_provider is None:
        resolved_vision_provider = settings.resolved_vision_provider()
    audit = repository.get_audit(audit_id)
    if audit is None:
        logger.error("process_audit called for unknown audit_id=%s", audit_id)
        return

    def progress(message: str) -> None:
        repository.update_audit_status(audit_id, "processing", status_message=message)

    try:
        progress("starting analysis")
        media_bytes = storage.read(audit.media_url)
        suffix = Path(audit.media_url).suffix or (".jpg" if audit.media_type == "image" else ".mp4")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(media_bytes)
            tmp_path = Path(tmp.name)

        try:
            vision_client = build_vision_client(
                resolved_vision_provider,
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_vision_model,
                groq_api_key=settings.groq_api_key,
                groq_model=settings.groq_vision_model,
            )
            catalog = ProductCatalog(repository.list_products())

            shelf_audit, pipeline_trace = run_extraction(
                media_path=tmp_path,
                media_type=audit.media_type,
                account_id=str(audit.account_id),
                media_reference=audit.media_url,
                vision_client=vision_client,
                catalog=catalog,
                settings=settings,
                on_progress=progress,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        audit_json = shelf_audit.model_dump(mode="json")
        audit_json["pipeline_trace"] = pipeline_trace
        repository.complete_audit(audit_id, audit_json)

    except Exception as exc:  # noqa: BLE001 - top-level pipeline guard, must never propagate
        logger.exception("audit pipeline failed for audit_id=%s", audit_id)
        repository.update_audit_status(audit_id, "failed", error_message=str(exc))
