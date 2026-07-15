import type { FrameQualityRecord } from "../types/audit";

function QualityChip({ label, value }: { label: string; value: number }) {
  return (
    <span className="text-[10px] text-gray-500">
      {label} <span className="font-medium text-gray-700">{value.toFixed(1)}</span>
    </span>
  );
}

function FrameTile({ record }: { record: FrameQualityRecord }) {
  return (
    <div
      className={`overflow-hidden rounded-lg border ${
        record.selected ? "border-emerald-300 ring-1 ring-emerald-200" : "border-gray-200"
      } bg-white`}
    >
      <div className="relative aspect-video bg-gray-100">
        {record.thumbnail ? (
          <img src={record.thumbnail} alt={record.frame_id} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[10px] text-gray-400">no thumbnail</div>
        )}
        <span
          className={`absolute left-1.5 top-1.5 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
            record.selected ? "bg-emerald-600 text-white" : "bg-gray-800/80 text-white"
          }`}
        >
          {record.selected ? "Used" : "Rejected"}
        </span>
      </div>
      <div className="space-y-1 p-2">
        <p className="truncate text-[11px] font-medium text-gray-700" title={record.frame_id}>
          {record.frame_id} <span className="text-gray-400">&middot; t={record.timestamp_sec.toFixed(2)}s</span>
        </p>
        <div className="flex flex-wrap gap-x-2">
          <QualityChip label="quality" value={record.quality_score} />
          <QualityChip label="blur" value={record.blur_score} />
          <QualityChip label="brightness" value={record.brightness_score} />
        </div>
        {record.rejection_reason && <p className="text-[11px] text-amber-700">Reason: {record.rejection_reason}</p>}
      </div>
    </div>
  );
}

/** "Analyzed Media" section: every frame the pipeline evaluated - selected
 * for vision analysis or rejected (and why) - with thumbnails, so a reviewer
 * can visually verify the frame-selection decision instead of trusting it
 * blindly. Works uniformly for images (one frame) and videos (many). */
export function FrameGallery({ records }: { records: FrameQualityRecord[] }) {
  if (records.length === 0) {
    return <p className="text-sm italic text-gray-400">No frame-level quality data was recorded for this audit.</p>;
  }

  const selected = records.filter((r) => r.selected);
  const rejected = records.filter((r) => !r.selected);

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        {selected.length} frame(s) used for vision analysis &middot; {rejected.length} rejected out of {records.length} sampled
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {records.map((r) => (
          <FrameTile record={r} key={r.frame_id} />
        ))}
      </div>
    </div>
  );
}
