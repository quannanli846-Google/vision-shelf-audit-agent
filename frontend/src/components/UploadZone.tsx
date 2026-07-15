import { useEffect, useRef, useState } from "react";
import { formatBytes } from "../lib/format";

const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".mp4", ".mov"];
const ACCEPTED_MIME_PREFIXES = ["image/", "video/"];
const DEFAULT_MAX_SIZE_MB = 200;

interface UploadZoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  maxSizeMB?: number;
}

function validateFile(file: File, maxSizeMB: number): string | null {
  const lowerName = file.name.toLowerCase();
  const hasAcceptedExtension = ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  const hasAcceptedMime = ACCEPTED_MIME_PREFIXES.some((prefix) => file.type.startsWith(prefix));
  if (!hasAcceptedExtension && !hasAcceptedMime) {
    return `Unsupported file type "${file.name.split(".").pop() ?? "unknown"}". Accepted: .jpg, .png, .mp4, .mov`;
  }
  const sizeMB = file.size / (1024 * 1024);
  if (sizeMB > maxSizeMB) {
    return `File is ${sizeMB.toFixed(1)}MB, which exceeds the ${maxSizeMB}MB limit.`;
  }
  return null;
}

function mediaKind(file: File): "image" | "video" {
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("image/")) return "image";
  return /\.(mp4|mov)$/i.test(file.name) ? "video" : "image";
}

/** Drag-and-drop (or click-to-browse) media uploader with an inline
 * preview, filename, media-type badge, and file size. Validates file type
 * and size client-side before the parent ever calls the API, so a bad
 * upload is caught instantly instead of round-tripping to the server. */
export function UploadZone({ file, onFileChange, maxSizeMB = DEFAULT_MAX_SIZE_MB }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFiles = (files: FileList | null) => {
    const selected = files?.[0];
    if (!selected) return;
    const validationError = validateFile(selected, maxSizeMB);
    if (validationError) {
      setError(validationError);
      onFileChange(null);
      return;
    }
    setError(null);
    onFileChange(selected);
  };

  if (file) {
    const kind = mediaKind(file);
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex gap-4">
          <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100">
            {previewUrl && kind === "image" && <img src={previewUrl} alt="preview" className="h-full w-full object-cover" />}
            {previewUrl && kind === "video" && <video src={previewUrl} className="h-full w-full object-cover" muted />}
          </div>
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
            <p className="truncate text-sm font-semibold text-gray-900">{file.name}</p>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 font-medium capitalize text-gray-700">
                {kind}
              </span>
              <span>{formatBytes(file.size)}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onFileChange(null)}
            className="h-fit rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          >
            Remove
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          isDragging ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100"
        }`}
      >
        <svg className="mb-3 h-9 w-9 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 7.5 7.5 12M12 7.5V16.5" />
        </svg>
        <p className="text-sm font-medium text-gray-700">Drag and drop a shelf image or video, or click to browse</p>
        <p className="mt-1 text-xs text-gray-500">.jpg, .png, .mp4, .mov - up to {maxSizeMB}MB</p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={[...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_PREFIXES.map((p) => `${p}*`)].join(",")}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200">{error}</p>
      )}
    </div>
  );
}
