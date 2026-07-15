import { useState } from "react";
import type { ExtractedField, ProductObserved } from "../types/audit";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { ConfidenceFactorBars } from "./ConfidenceFactorBars";
import { ReviewActions } from "./ReviewActions";
import { CONFIDENCE_TIER_STYLES, getConfidenceTier } from "../lib/confidence";

function productTitle(product: ProductObserved): string {
  const parts = [product.brand.value, product.product_name.value].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : "Unknown bottle";
}

/** The single most relevant "why is this uncertain" reason for a product -
 * whichever core field is null first, otherwise the lowest-confidence field.
 * Used to surface one clear explanation in the Needs Review section instead
 * of forcing the reviewer to scan five separate reasons. */
function primaryUncertainty(product: ProductObserved): ExtractedField<unknown> {
  const ordered = [product.brand, product.product_name, product.size, product.facings, product.shelf_level];
  const firstNull = ordered.find((f) => f.value === null);
  if (firstNull) return firstNull;
  return ordered.reduce((lowest, f) => (f.confidence < lowest.confidence ? f : lowest));
}

/** Evidence lines are plain sentences built server-side from validated
 * reasons (never invented in the UI) - this only decides whether a given
 * line reads as supporting or undermining the observation, for a
 * checkmark/warning icon. */
function isNegativeEvidence(line: string): boolean {
  const lower = line.toLowerCase();
  return lower.includes("not identified") || lower.includes("not legible") || lower.startsWith("no catalog match");
}

function EvidenceList({ evidence }: { evidence: string[] }) {
  if (evidence.length === 0) return null;
  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Evidence</p>
      <ul className="mt-1.5 space-y-1">
        {evidence.map((line, i) => (
          <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
            <span className={isNegativeEvidence(line) ? "text-amber-500" : "text-emerald-500"}>
              {isNegativeEvidence(line) ? "\u26a0" : "\u2713"}
            </span>
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ProductCardProps {
  product: ProductObserved;
  /** "grid" renders the full detail card (Detected Products section).
   * "review" renders a more compact, reason-forward card (Needs Review section). */
  variant?: "grid" | "review";
  /** Required to show human-review (Confirm/Correct/Reject) controls on
   * "review" cards - omit to render the card read-only (e.g. in a context
   * with no persisted audit yet). */
  auditId?: string;
  /** Index within `products_observed`, used to build a stable feedback
   * field path like "products_observed[2].brand". */
  index?: number;
}

export function ProductCard({ product, variant = "grid", auditId, index }: ProductCardProps) {
  const [showFactors, setShowFactors] = useState(false);
  const tier = getConfidenceTier(product.overall_confidence);
  const styles = CONFIDENCE_TIER_STYLES[tier];

  if (variant === "review") {
    const reason = primaryUncertainty(product);
    const reviewedField = reason === product.brand ? "brand" : reason === product.product_name ? "product_name" : "field";
    return (
      <div className={`rounded-lg border-l-4 ${styles.border} border border-gray-200 bg-white p-4 shadow-sm`}>
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-semibold text-gray-900">{productTitle(product)}</h4>
          <ConfidenceBadge score={product.overall_confidence} size="sm" />
        </div>
        <p className="mt-1 text-xs font-medium uppercase tracking-wide text-gray-400">Reason</p>
        <p className="text-sm text-gray-700">{reason.reason}</p>
        <EvidenceList evidence={product.evidence} />
        {auditId && index !== undefined && (
          <ReviewActions
            auditId={auditId}
            field={`products_observed[${index}].${reviewedField}`}
            aiValue={(reason.value as string | null) ?? null}
            aiConfidence={reason.confidence}
          />
        )}
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-4 shadow-sm ${tier === "low" ? `border-l-4 ${styles.border}` : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-semibold text-gray-900">{productTitle(product)}</h4>
        <ConfidenceBadge score={product.overall_confidence} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs font-medium text-gray-500">Size</dt>
          <dd className={product.size.value ? "text-gray-900" : "italic text-gray-400"}>{product.size.value ?? "Not identified"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">Facings</dt>
          <dd className={product.facings.value !== null ? "text-gray-900" : "italic text-gray-400"}>
            {product.facings.value ?? "Not identified"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">Shelf position</dt>
          <dd className={product.shelf_level.value ? "text-gray-900" : "italic text-gray-400"}>
            {product.shelf_level.value ?? "Not identified"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">Catalog match</dt>
          <dd className={product.matched_sku.value ? "truncate text-gray-900" : "italic text-gray-400"} title={product.matched_sku.reason}>
            {product.matched_sku.value ? product.matched_sku.value.split(": ").slice(1).join(": ") : "Not matched"}
          </dd>
        </div>
      </dl>

      {product.source_frames.length > 1 && (
        <p className="mt-3 text-xs font-medium text-blue-600">Corroborated across {product.source_frames.length} frames</p>
      )}

      <EvidenceList evidence={product.evidence} />

      <div className="mt-3 border-t border-gray-100 pt-3">
        <button
          type="button"
          onClick={() => setShowFactors((v) => !v)}
          className="text-xs font-medium text-blue-600 hover:text-blue-700"
        >
          {showFactors ? "Hide" : "Show"} confidence breakdown
        </button>
        {showFactors && (
          <div className="mt-2">
            <ConfidenceFactorBars factors={product.confidence.factors} />
          </div>
        )}
      </div>
    </div>
  );
}
