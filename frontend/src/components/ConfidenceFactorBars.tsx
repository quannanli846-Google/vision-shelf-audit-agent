import type { ConfidenceFactors } from "../types/audit";

const FACTOR_LABELS: Record<keyof ConfidenceFactors, string> = {
  vision: "Vision",
  ocr: "Label / OCR",
  catalog_match: "Catalog match",
  frame_consistency: "Frame consistency",
};

const FACTOR_ORDER: Array<keyof ConfidenceFactors> = ["vision", "ocr", "catalog_match", "frame_consistency"];

/** Small, non-dashboard breakdown of the four signals that feed
 * `overall_confidence` - mirrors ConfidenceFactors in
 * backend/models/shelf_audit.py. Intentionally just labeled bars, not a
 * chart library, per the "don't over-invest in UI" guidance. */
export function ConfidenceFactorBars({ factors }: { factors: ConfidenceFactors }) {
  return (
    <div className="space-y-1.5">
      {FACTOR_ORDER.map((key) => {
        const pct = Math.round(factors[key] * 100);
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="w-28 shrink-0 text-[11px] text-gray-500">{FACTOR_LABELS[key]}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100">
              <div className="h-full rounded-full bg-blue-400" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-9 shrink-0 text-right text-[11px] text-gray-500">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}
