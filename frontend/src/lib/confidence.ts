// Shared confidence-tier logic so every component (ConfidenceBadge,
// ProductCard, HistoryPage, ...) agrees on the same thresholds.
//
// These thresholds are a UI-level display convention (High >= 0.8,
// Medium 0.5-0.8, Low < 0.5) and are intentionally distinct from the
// backend's own calibration thresholds (default 0.75/0.4) used to derive
// `confidence_level` - the backend's thresholds govern calibration logic,
// these govern how confidence is *communicated* to a field rep reviewing
// results.

export type ConfidenceTier = "high" | "medium" | "low";

export function getConfidenceTier(score: number): ConfidenceTier {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

export const CONFIDENCE_TIER_STYLES: Record<ConfidenceTier, { badge: string; dot: string; border: string; text: string }> = {
  high: {
    badge: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-600/20",
    dot: "bg-emerald-500",
    border: "border-emerald-200",
    text: "text-emerald-700",
  },
  medium: {
    badge: "bg-amber-100 text-amber-800 ring-1 ring-amber-600/20",
    dot: "bg-amber-500",
    border: "border-amber-200",
    text: "text-amber-700",
  },
  low: {
    badge: "bg-rose-100 text-rose-800 ring-1 ring-rose-600/20",
    dot: "bg-rose-500",
    border: "border-rose-200",
    text: "text-rose-700",
  },
};

export function formatConfidencePct(score: number): string {
  return `${Math.round(score * 100)}%`;
}
