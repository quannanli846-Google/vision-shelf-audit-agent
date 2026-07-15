import type { ReactNode } from "react";

export type TimelineStepStatus = "done" | "active" | "pending" | "skipped" | "error";

export interface TimelineStep {
  id: string;
  label: string;
  status: TimelineStepStatus;
  detail?: ReactNode;
}

const LABEL_CLASSES: Record<TimelineStepStatus, string> = {
  done: "text-gray-900 font-medium",
  active: "text-blue-700 font-semibold",
  pending: "text-gray-400",
  skipped: "text-gray-400",
  error: "text-rose-700 font-semibold",
};

function StepIcon({ status }: { status: TimelineStepStatus }) {
  const base = "flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-4 ring-white";
  switch (status) {
    case "done":
      return (
        <span className={`${base} bg-emerald-500 text-white`}>
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0l-3.5-3.5a1 1 0 1 1 1.4-1.4l2.8 2.8 6.8-6.8a1 1 0 0 1 1.4 0Z" clipRule="evenodd" />
          </svg>
        </span>
      );
    case "active":
      return (
        <span className={`${base} bg-blue-600 text-white`}>
          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-90" fill="currentColor" d="M12 2a10 10 0 0 1 10 10h-4a6 6 0 0 0-6-6V2Z" />
          </svg>
        </span>
      );
    case "error":
      return (
        <span className={`${base} bg-rose-500 text-white`}>
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM8.7 7.3a1 1 0 0 1 1.4 0l0 0 1.4 1.4 1.4-1.4a1 1 0 1 1 1.4 1.4L12.9 10l1.4 1.4a1 1 0 0 1-1.4 1.4L11.5 11.4l-1.4 1.4a1 1 0 0 1-1.4-1.4L10.1 10 8.7 8.6a1 1 0 0 1 0-1.3Z" clipRule="evenodd" />
          </svg>
        </span>
      );
    case "skipped":
      return <span className={`${base} bg-gray-100 text-gray-400 ring-1 ring-inset ring-gray-300`}>-</span>;
    default:
      return <span className={`${base} bg-white text-transparent ring-1 ring-inset ring-gray-300`}>&nbsp;</span>;
  }
}

/** Generic vertical step timeline - reused for both the live "processing"
 * view on the Upload page and the historical AI Processing Trace panel on
 * the Audit Result page, so both share exactly one visual language for
 * "what stage is this audit at". */
export function StatusTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol>
      {steps.map((step, i) => (
        <li key={step.id} className="relative flex gap-3 pb-6 last:pb-0">
          {i < steps.length - 1 && <span className="absolute left-3 top-6 h-[calc(100%-1.5rem)] w-px bg-gray-200" />}
          <StepIcon status={step.status} />
          <div className="min-w-0 flex-1 pt-0.5">
            <p className={`text-sm ${LABEL_CLASSES[step.status]}`}>{step.label}</p>
            {step.detail && <div className="mt-1 text-sm text-gray-500">{step.detail}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}
