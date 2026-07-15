import { useState } from "react";
import type { ShelfAudit } from "../types/audit";
import { StatusTimeline, type TimelineStep } from "./StatusTimeline";
import { formatDateTime } from "../lib/format";

function buildTraceSteps(audit: ShelfAudit): TimelineStep[] {
  const trace = audit.pipeline_trace;
  const isVideo = audit.media_type === "video";
  const totalDetected =
    audit.products_observed.length +
    audit.out_of_stock_signals.length +
    audit.shelf_positions.length +
    audit.promotions.length +
    audit.pricing_reads.length +
    audit.compliance_flags.length;
  const matchedCount = audit.products_observed.filter((p) => p.matched_sku.value !== null).length;
  const summary = audit.confidence_summary;

  const steps: TimelineStep[] = [
    {
      id: "uploaded",
      label: "Media uploaded",
      status: "done",
      detail: `${isVideo ? "Video" : "Image"} received and stored`,
    },
  ];

  if (isVideo) {
    steps.push({
      id: "frames",
      label: "Frames extracted",
      status: trace ? "done" : "skipped",
      detail: trace ? `${trace.frames_sampled} frame(s) sampled from the video` : "No trace recorded for this audit",
    });
    steps.push({
      id: "quality",
      label: "Quality filtering",
      status: trace ? "done" : "skipped",
      detail: trace
        ? `${trace.frames_kept} frame(s) kept, ${trace.frames_rejected.length} rejected (blur, dark, glare, or duplicate) - see Analyzed Media below`
        : "No trace recorded for this audit",
    });
  } else {
    steps.push({ id: "frames", label: "Frames extracted", status: "skipped", detail: "Skipped - images are analyzed directly" });
    steps.push({ id: "quality", label: "Quality filtering", status: "skipped", detail: "Skipped - images are analyzed directly" });
  }

  steps.push({
    id: "vision",
    label: "Vision extraction",
    status: "done",
    detail: `Provider: ${trace?.vision_provider ?? "Unknown"} \u00b7 Frames analyzed: ${
      trace?.frames_selected.length ?? summary.frames_analyzed
    } \u00b7 Detected objects: ${totalDetected}`,
  });

  steps.push({
    id: "grounding",
    label: "SKU grounding",
    status: "done",
    detail: `${matchedCount} of ${audit.products_observed.length} product(s) matched to the reference catalog`,
  });

  steps.push({
    id: "calibration",
    label: "Confidence calibration",
    status: "done",
    detail: `Overall confidence ${(summary.overall_confidence * 100).toFixed(0)}% \u2014 ${summary.high_count} high / ${summary.medium_count} medium / ${summary.low_count} low`,
  });

  steps.push({
    id: "generated",
    label: "Audit generated",
    status: "done",
    detail: `Generated ${formatDateTime(audit.generated_at)}`,
  });

  return steps;
}

/** Collapsible "AI Processing Trace" panel. Maps the pipeline's actual
 * internals (frame sampling/rejection, raw per-frame model output,
 * validation warnings) onto the conceptual pipeline stages, so a reviewer
 * can see the full extraction -> validation -> grounding -> calibration
 * chain, not just the polished final result. */
export function AuditTrace({ audit }: { audit: ShelfAudit }) {
  const [open, setOpen] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const steps = buildTraceSteps(audit);
  const trace = audit.pipeline_trace;

  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
        aria-expanded={open}
      >
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-900">AI Processing Trace</h3>
            {trace?.vision_provider && (
              <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-blue-200">
                Vision Provider: {trace.vision_provider}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500">See exactly how this audit was produced, step by step</p>
        </div>
        <svg
          className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path fillRule="evenodd" d="M5.2 7.2a1 1 0 0 1 1.4 0L10 10.6l3.4-3.4a1 1 0 1 1 1.4 1.4l-4.1 4.1a1 1 0 0 1-1.4 0L5.2 8.6a1 1 0 0 1 0-1.4Z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-5">
          <StatusTimeline steps={steps} />

          {trace && (
            <div className="mt-4 border-t border-gray-100 pt-4">
              {trace.validation_warnings.length > 0 && (
                <div className="mb-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
                  <p className="mb-1 font-semibold">Validation warnings ({trace.validation_warnings.length})</p>
                  <ul className="list-disc space-y-0.5 pl-4">
                    {trace.validation_warnings.slice(0, 5).map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              <button
                type="button"
                onClick={() => setShowRaw((v) => !v)}
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                {showRaw ? "Hide" : "Show"} raw pipeline data (per-frame model output before validation)
              </button>
              {showRaw && (
                <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-gray-900 p-3 text-[11px] leading-relaxed text-gray-200">
                  {JSON.stringify(trace, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
