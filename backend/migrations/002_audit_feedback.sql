-- Vision AI Shelf Audit - human review feedback loop
-- Run this in the Supabase SQL editor AFTER 001_init.sql.
--
-- Design note: this is an APPEND-ONLY log of reviewer decisions on
-- individual AI-extracted fields. It intentionally never mutates
-- `audits.audit_json` - the audit record always reflects exactly what the
-- pipeline produced at completion time, and every human correction is kept
-- as a separate, timestamped, auditable event for future evaluation /
-- confidence-calibration work (e.g. "how often is a 'low' confidence field
-- actually wrong?").

create table if not exists audit_feedback (
    id              uuid primary key default gen_random_uuid(),
    audit_id        uuid not null references audits(id) on delete cascade,
    field           text not null,
    review_action   text not null check (review_action in ('confirm', 'correct', 'reject')),
    ai_value        text,
    ai_confidence   double precision check (ai_confidence is null or (ai_confidence >= 0 and ai_confidence <= 1)),
    corrected_value text,
    created_at      timestamptz not null default now()
);

create index if not exists idx_audit_feedback_audit_id on audit_feedback(audit_id);
