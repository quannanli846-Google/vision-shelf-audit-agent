import { useState } from "react";
import { auditsApi } from "../api/audits";
import type { ReviewAction } from "../types/audit";

interface ReviewActionsProps {
  auditId: string;
  /** Path identifying the reviewed field, e.g. "products_observed[2].brand" -
   * persisted verbatim to audit_feedback.field. */
  field: string;
  aiValue: string | null;
  aiConfidence: number;
}

const DONE_LABELS: Record<ReviewAction, string> = {
  confirm: "Confirmed by reviewer",
  correct: "Corrected by reviewer",
  reject: "Rejected by reviewer",
};

/** Human review loop controls for one low-confidence field: Confirm / Correct
 * / Reject. Submits to `POST /api/audits/{id}/feedback` - an append-only log
 * that never mutates the underlying audit, so re-reviewing is always safe. */
export function ReviewActions({ auditId, field, aiValue, aiConfidence }: ReviewActionsProps) {
  const [mode, setMode] = useState<"idle" | "correcting" | "submitting">("idle");
  const [correctedValue, setCorrectedValue] = useState("");
  const [doneAction, setDoneAction] = useState<ReviewAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (action: ReviewAction, corrected?: string) => {
    setMode("submitting");
    setError(null);
    try {
      await auditsApi.submitFeedback(auditId, {
        field,
        review_action: action,
        ai_value: aiValue,
        ai_confidence: aiConfidence,
        corrected_value: corrected ?? null,
      });
      setDoneAction(action);
    } catch {
      setError("Could not save your review - please try again.");
      setMode("idle");
    }
  };

  if (doneAction) {
    return <p className="mt-2 text-xs font-medium text-emerald-700">{"\u2713 " + DONE_LABELS[doneAction]}</p>;
  }

  if (mode === "correcting") {
    return (
      <form
        className="mt-2 flex items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (correctedValue.trim()) submit("correct", correctedValue.trim());
        }}
      >
        <input
          autoFocus
          value={correctedValue}
          onChange={(e) => setCorrectedValue(e.target.value)}
          placeholder="Correct value..."
          className="min-w-0 flex-1 rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-blue-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!correctedValue.trim()}
          className="shrink-0 rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Save
        </button>
        <button type="button" onClick={() => setMode("idle")} className="shrink-0 text-xs text-gray-500 hover:underline">
          Cancel
        </button>
      </form>
    );
  }

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={mode === "submitting"}
          onClick={() => submit("confirm")}
          className="rounded-md border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
        >
          Confirm
        </button>
        <button
          type="button"
          disabled={mode === "submitting"}
          onClick={() => setMode("correcting")}
          className="rounded-md border border-blue-300 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
        >
          Correct
        </button>
        <button
          type="button"
          disabled={mode === "submitting"}
          onClick={() => submit("reject")}
          className="rounded-md border border-rose-300 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
