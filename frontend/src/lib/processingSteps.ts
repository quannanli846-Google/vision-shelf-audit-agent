import type { Audit } from "../types/audit";
import type { TimelineStep } from "../components/StatusTimeline";

const STAGE_ORDER = ["upload", "frames", "vision", "grounding", "calibration"] as const;
type Stage = (typeof STAGE_ORDER)[number];

/** Infers which pipeline stage is currently running from the backend's
 * free-text `status_message` (set by services/audit_pipeline.py's
 * `progress()` callback). This is a best-effort mapping for UX purposes
 * only - if the message doesn't match anything recognized, we fall back to
 * whichever stage is first for that media type. */
function currentStage(mediaType: Audit["media_type"], statusMessage: string | null): Stage {
  const msg = (statusMessage ?? "").toLowerCase();
  if (msg.includes("calibrating confidence")) return "calibration";
  if (msg.includes("grounding products")) return "grounding";
  if (msg.includes("analyzing frame") || msg.includes("analyzing image")) return "vision";
  if (msg.includes("extracting video frames") || msg.includes("filtering low-quality frames")) return "frames";
  return mediaType === "video" ? "frames" : "vision";
}

const STAGE_LABELS: Record<Stage, string> = {
  upload: "Uploading media",
  frames: "Extracting frames",
  vision: "Running vision analysis",
  grounding: "Matching products",
  calibration: "Generating shelf audit",
};

/** Builds the 5-step "Step 1: Uploading media..." timeline shown while an
 * audit is uploaded/processing. Frame extraction is skipped (not faked as
 * "done") for image uploads, which are analyzed directly. */
export function buildProcessingSteps(audit: Audit): TimelineStep[] {
  const isVideo = audit.media_type === "video";
  const isFailed = audit.status === "failed";
  const isCompleted = audit.status === "completed";
  const stage = currentStage(audit.media_type, audit.status_message);
  const stageIdx = STAGE_ORDER.indexOf(stage);

  return STAGE_ORDER.map((id, idx) => {
    const label = STAGE_LABELS[id];

    if (id === "frames" && !isVideo) {
      return { id, label, status: "skipped", detail: "Not needed - images are analyzed directly" };
    }
    if (isCompleted) {
      return { id, label, status: "done" };
    }
    if (idx < stageIdx) {
      return { id, label, status: "done" };
    }
    if (idx === stageIdx) {
      if (isFailed) {
        return { id, label, status: "error", detail: audit.error_message ?? "This step failed" };
      }
      return { id, label: `${label}...`, status: "active" };
    }
    return { id, label, status: "pending" };
  });
}
