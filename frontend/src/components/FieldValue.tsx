import type { ExtractedField } from "../types/audit";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface FieldValueProps<T> {
  field: ExtractedField<T>;
  label?: string;
}

/** Renders one ExtractedField<T>: its value (or an explicit "Not identified"
 * fallback - never blank, never guessed), a confidence badge, and the
 * model's reason/evidence directly underneath. This is the single place
 * that turns the backend's {value, confidence, reason} contract into UI, so
 * uncertainty is always visible rather than hidden behind a clean-looking
 * blank field. */
export function FieldValue<T>({ field, label }: FieldValueProps<T>) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        {label && <span className="text-xs font-medium text-gray-500">{label}</span>}
        <span className={field.value === null ? "text-sm italic text-gray-400" : "text-sm font-medium text-gray-900"}>
          {field.value === null ? "Not identified" : String(field.value)}
        </span>
        <ConfidenceBadge score={field.confidence} size="sm" />
      </div>
      <p className="mt-0.5 truncate text-xs text-gray-500" title={field.reason}>
        {field.reason}
      </p>
    </div>
  );
}
