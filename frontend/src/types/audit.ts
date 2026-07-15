// Strict TypeScript mirror of backend/models/shelf_audit.py and
// backend/models/db_models.py. Keeping this file in lockstep with the
// backend schemas is what lets the rest of the frontend stay fully typed
// with no `any`.

export type ConfidenceLevel = "high" | "medium" | "low";

/** Generic {value, confidence, reason} wrapper - mirrors ExtractedField[T] in
 * backend/models/shelf_audit.py. A null `value` always means "the model
 * could not confidently determine this" - never treat it as a rendering bug. */
export interface ExtractedField<T> {
  value: T | null;
  confidence: number;
  confidence_level: ConfidenceLevel;
  reason: string;
}

/** The individual signals `overall_confidence` is derived from - mirrors
 * ConfidenceFactors in backend/models/shelf_audit.py. `ocr` and `vision` are
 * documented approximations (there's no separate OCR engine - the VLM reads
 * label text jointly with visual recognition), not literal independent
 * measurements; see docs/DESIGN_NOTES.md. */
export interface ConfidenceFactors {
  vision: number;
  ocr: number;
  catalog_match: number;
  frame_consistency: number;
}

export interface ConfidenceBreakdown {
  overall: number;
  factors: ConfidenceFactors;
}

export interface ProductObserved {
  brand: ExtractedField<string>;
  product_name: ExtractedField<string>;
  size: ExtractedField<string>;
  facings: ExtractedField<number>;
  shelf_level: ExtractedField<string>;
  matched_sku: ExtractedField<string>;
  overall_confidence: number;
  confidence: ConfidenceBreakdown;
  evidence: string[];
  source_frames: string[];
}

export interface OutOfStockSignal {
  location: ExtractedField<string>;
  likely_product: ExtractedField<string>;
  overall_confidence: number;
}

export interface ShelfPosition {
  level: ExtractedField<string>;
  description: ExtractedField<string>;
  overall_confidence: number;
}

export interface Promotion {
  promo_type: ExtractedField<string>;
  text_detected: ExtractedField<string>;
  associated_product: ExtractedField<string>;
  overall_confidence: number;
}

export interface PricingRead {
  product: ExtractedField<string>;
  price: ExtractedField<string>;
  overall_confidence: number;
}

export interface ComplianceFlag {
  issue_type: ExtractedField<string>;
  description: ExtractedField<string>;
  overall_confidence: number;
}

export interface ShareOfShelf {
  by_brand: Record<string, number>;
  total_facings_counted: number;
  confidence: number;
  reason: string;
}

export interface ConfidenceSummary {
  overall_confidence: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  frames_analyzed: number;
  warnings: string[];
}

export interface RejectedFrame {
  frame_id: string;
  timestamp_sec: number;
  reason: string;
  blur_score: number;
}

/** One record per sampled frame - selected, defect-rejected (blur/dark/
 * glare/duplicate), or simply outcompeted for a selection slot - mirrors
 * FrameQualityRecord in backend/video/quality_filter.py. `thumbnail`, when
 * present, is a ready-to-render base64 data URI (bounded to a small gallery
 * subset server-side, never every sampled frame). */
export interface FrameQualityRecord {
  frame_id: string;
  timestamp_sec: number;
  blur_score: number;
  brightness_score: number;
  quality_score: number;
  selected: boolean;
  rejection_reason: string | null;
  thumbnail?: string;
}

export interface PipelineTrace {
  media_type: string;
  /** Human-readable label for whichever VisionClient produced this audit
   * (e.g. "OpenAI Vision", "Groq Vision", "Mock Vision") - the perception
   * backend is a swappable implementation detail, but which one ran is
   * always shown for transparency. */
  vision_provider: string;
  frames_sampled: number;
  frames_kept: number;
  frames_selected: string[];
  frames_rejected: RejectedFrame[];
  frame_quality_records: FrameQualityRecord[];
  raw_model_outputs: Record<string, string>;
  validation_warnings: string[];
}

/** What `GET /api/audits/{id}/trace` returns - `available` is false until
 * the audit has completed (or if no trace was recorded), never faked. */
export type AuditTraceResponse = ({ available: true } & PipelineTrace) | { available: false; reason: string };

export interface ShelfAudit {
  account_id: string;
  media_reference: string;
  media_type: "image" | "video";
  products_observed: ProductObserved[];
  out_of_stock_signals: OutOfStockSignal[];
  shelf_positions: ShelfPosition[];
  promotions: Promotion[];
  pricing_reads: PricingRead[];
  compliance_flags: ComplianceFlag[];
  share_of_shelf: ShareOfShelf;
  notes: string;
  confidence_summary: ConfidenceSummary;
  generated_at: string;
  pipeline_trace?: PipelineTrace;
}

export type AuditStatus = "uploaded" | "processing" | "completed" | "failed";
export type MediaType = "image" | "video";

export interface Account {
  id: string;
  store_name: string;
  created_at: string;
}

export interface Product {
  id: string;
  brand: string;
  product_name: string;
  size: string | null;
  aliases: string[];
}

export interface AuditCreateResponse {
  id: string;
  status: AuditStatus;
}

export interface Audit {
  id: string;
  account_id: string;
  media_url: string;
  media_type: MediaType;
  status: AuditStatus;
  status_message: string | null;
  audit_json: ShelfAudit | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

/** Row shape for the History page table - enriched server-side with
 * store_name + overall_confidence so the frontend never needs to fetch a
 * full audit_json just to render a list. */
export interface AuditListItem {
  id: string;
  account_id: string;
  store_name: string;
  media_type: MediaType;
  status: AuditStatus;
  overall_confidence: number | null;
  created_at: string;
}

/** Human review loop: mirrors AuditFeedback / AuditFeedbackCreate in
 * backend/models/db_models.py. This is an append-only log - submitting
 * feedback never changes the underlying audit_json. */
export type ReviewAction = "confirm" | "correct" | "reject";

export interface AuditFeedback {
  id: string;
  audit_id: string;
  field: string;
  review_action: ReviewAction;
  ai_value: string | null;
  ai_confidence: number | null;
  corrected_value: string | null;
  created_at: string;
}

export interface AuditFeedbackCreate {
  field: string;
  review_action: ReviewAction;
  ai_value?: string | null;
  ai_confidence?: number | null;
  corrected_value?: string | null;
}

/** Developer/demo-only "Vision Provider" switch - mirrors
 * backend/models/vision_settings.py. This is NOT a field-representative
 * feature: it exists purely so a demo can flip between Mock Vision and a
 * real provider live. Production deployments configure the provider via the
 * `VISION_PROVIDER` environment variable instead (see README.md). */
export type VisionProviderName = "mock" | "openai" | "groq";

export interface VisionProviderOption {
  provider: VisionProviderName;
  label: string;
  mode_label: string;
  description: string;
  available: boolean;
  unavailable_reason: string | null;
}

export interface VisionProviderStatus {
  active_provider: VisionProviderName;
  label: string;
  mode_label: string;
  description: string;
  is_dev_override: boolean;
  default_provider: VisionProviderName;
  options: VisionProviderOption[];
}
