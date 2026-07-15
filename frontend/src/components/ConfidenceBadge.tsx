import { CONFIDENCE_TIER_STYLES, formatConfidencePct, getConfidenceTier } from "../lib/confidence";

interface ConfidenceBadgeProps {
  score: number;
  size?: "sm" | "md";
  className?: string;
}

/** Renders a numeric confidence score as a colored pill (High >= 0.8,
 * Medium 0.5-0.8, Low < 0.5). Used everywhere a confidence number appears
 * so the color language stays consistent across the app. */
export function ConfidenceBadge({ score, size = "md", className = "" }: ConfidenceBadgeProps) {
  const tier = getConfidenceTier(score);
  const styles = CONFIDENCE_TIER_STYLES[tier];
  const sizeClasses = size === "sm" ? "text-[11px] px-1.5 py-0.5" : "text-xs px-2 py-1";

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full font-semibold whitespace-nowrap ${sizeClasses} ${styles.badge} ${className}`}
      title={`confidence score: ${score.toFixed(2)}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} />
      {formatConfidencePct(score)}
    </span>
  );
}
