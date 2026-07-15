from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form

from config import Settings, get_settings
from database.dependencies import get_repository, get_storage
from database.repository import AuditRepository
from database.storage import MediaStorage
from models.db_models import Audit, AuditCreateResponse, AuditFeedback, AuditFeedbackCreate, AuditListItem
from services.audit_pipeline import process_audit
from services.vision_provider_state import VisionProviderState, get_vision_provider_state

router = APIRouter(prefix="/api/audits", tags=["audits"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}


def _resolve_media_type(filename: str, content_type: Optional[str]) -> str:
    lower_name = (filename or "").lower()
    if content_type:
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"
    for ext in IMAGE_EXTENSIONS:
        if lower_name.endswith(ext):
            return "image"
    for ext in VIDEO_EXTENSIONS:
        if lower_name.endswith(ext):
            return "video"
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type for '{filename}'. Allowed: {sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)}",
    )


@router.post("", response_model=AuditCreateResponse)
async def create_audit(
    background_tasks: BackgroundTasks,
    account_id: UUID = Form(...),
    file: UploadFile = File(...),
    repository: AuditRepository = Depends(get_repository),
    storage: MediaStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
    vision_provider_state: VisionProviderState = Depends(get_vision_provider_state),
) -> AuditCreateResponse:
    if repository.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    media_type = _resolve_media_type(file.filename or "", file.content_type)

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_size_mb}MB upload limit")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    media_url = storage.upload(file_bytes, file.filename or "upload", file.content_type or "application/octet-stream")
    audit = repository.create_audit(account_id, media_url, media_type)

    # Read the (possibly developer-overridden) active provider name now, at
    # upload time, rather than inside the background task - so the trace
    # always reflects the provider that was active when this specific audit
    # was submitted, even if someone flips the switch again a moment later.
    background_tasks.add_task(process_audit, audit.id, repository, storage, settings, vision_provider_state.active_provider)

    return AuditCreateResponse(id=audit.id, status=audit.status)


@router.get("", response_model=list[AuditListItem])
def list_audits(
    account_id: Optional[UUID] = None,
    repository: AuditRepository = Depends(get_repository),
) -> list[AuditListItem]:
    store_names = {acct.id: acct.store_name for acct in repository.list_accounts()}
    items: list[AuditListItem] = []
    for a in repository.list_audits(account_id):
        overall_confidence: Optional[float] = None
        if a.audit_json:
            overall_confidence = (a.audit_json.get("confidence_summary") or {}).get("overall_confidence")
        items.append(
            AuditListItem(
                id=a.id,
                account_id=a.account_id,
                store_name=store_names.get(a.account_id, "Unknown store"),
                media_type=a.media_type,
                status=a.status,
                overall_confidence=overall_confidence,
                created_at=a.created_at,
            )
        )
    return items


@router.get("/{audit_id}", response_model=Audit)
def get_audit(audit_id: UUID, repository: AuditRepository = Depends(get_repository)) -> Audit:
    audit = repository.get_audit(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return audit


@router.get("/{audit_id}/trace")
def get_audit_trace(audit_id: UUID, repository: AuditRepository = Depends(get_repository)) -> dict:
    """Reasoning-pipeline trace: frame sampling/rejection, raw per-frame model
    output pre-validation, and validation warnings. Exists to demonstrate the
    pipeline's reasoning, not for end-user consumption.
    """
    audit = repository.get_audit(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    if not audit.audit_json:
        return {"available": False, "reason": f"audit is still '{audit.status}' - no trace yet"}
    trace = audit.audit_json.get("pipeline_trace")
    if trace is None:
        return {"available": False, "reason": "no trace was recorded for this audit"}
    return {"available": True, **trace}


@router.post("/{audit_id}/feedback", response_model=AuditFeedback, status_code=201)
def create_audit_feedback(
    audit_id: UUID,
    payload: AuditFeedbackCreate,
    repository: AuditRepository = Depends(get_repository),
) -> AuditFeedback:
    """Human review loop: record a reviewer's Confirm/Correct/Reject decision
    on one AI-extracted field. This is an append-only log for future
    evaluation/calibration - it never mutates `audits.audit_json`, so the
    audit always reflects exactly what the pipeline produced.
    """
    if repository.get_audit(audit_id) is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return repository.create_feedback(audit_id, payload)


@router.get("/{audit_id}/feedback", response_model=list[AuditFeedback])
def list_audit_feedback(audit_id: UUID, repository: AuditRepository = Depends(get_repository)) -> list[AuditFeedback]:
    if repository.get_audit(audit_id) is None:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")
    return repository.list_feedback(audit_id)
