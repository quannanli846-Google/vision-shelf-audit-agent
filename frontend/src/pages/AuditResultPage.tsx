import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { ReactNode } from "react";
import { accountsApi } from "../api/accounts";
import { auditsApi } from "../api/audits";
import { ApiError, resolveMediaUrl } from "../api/client";
import type { Account, Audit } from "../types/audit";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { FieldValue } from "../components/FieldValue";
import { ProductCard } from "../components/ProductCard";
import { StatusTimeline } from "../components/StatusTimeline";
import { AuditTrace } from "../components/AuditTrace";
import { FrameGallery } from "../components/FrameGallery";
import { buildProcessingSteps } from "../lib/processingSteps";
import { formatDateTime } from "../lib/format";

const POLL_INTERVAL_MS = 2000;

function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-base font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-gray-400">{children}</p>;
}

export function AuditResultPage() {
  const { id } = useParams<{ id: string }>();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    accountsApi.list().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  useEffect(() => {
    if (!id) return;

    const poll = async () => {
      try {
        const result = await auditsApi.get(id);
        setAudit(result);
        setFetchError(null);
        if (result.status === "completed" || result.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.status === 404
              ? "This audit could not be found. It may have been removed."
              : err.message
            : "Failed to load this audit.";
        setFetchError(message);
        if (pollRef.current) clearInterval(pollRef.current);
      }
    };

    poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id]);

  const storeName = audit ? accounts.find((a) => a.id === audit.account_id)?.store_name ?? "Unknown store" : "";

  if (fetchError) {
    return (
      <div className="mx-auto max-w-2xl rounded-xl border border-rose-200 bg-rose-50 p-6">
        <h1 className="text-lg font-semibold text-rose-800">Couldn't load this audit</h1>
        <p className="mt-2 text-sm text-rose-700">{fetchError}</p>
        <Link to="/" className="mt-4 inline-block text-sm font-semibold text-blue-700 hover:underline">
          Back to New Audit
        </Link>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="mx-auto max-w-2xl rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
        Loading audit...
      </div>
    );
  }

  if (audit.status === "uploaded" || audit.status === "processing") {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="text-xl font-semibold text-gray-900">Analyzing shelf {audit.media_type}</h1>
        <p className="mt-1 text-sm text-gray-500">This updates automatically - no need to refresh.</p>
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <StatusTimeline steps={buildProcessingSteps(audit)} />
        </div>
      </div>
    );
  }

  if (audit.status === "failed") {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="rounded-xl border border-rose-200 bg-white p-6 shadow-sm">
          <h1 className="text-lg font-semibold text-rose-800">Audit processing failed</h1>
          <p className="mt-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200">
            {audit.error_message ?? "An unknown error occurred while processing this audit."}
          </p>
          <div className="mt-5">
            <StatusTimeline steps={buildProcessingSteps(audit)} />
          </div>
          <Link
            to="/"
            className="mt-5 inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Try another upload
          </Link>
        </div>
      </div>
    );
  }

  const shelfAudit = audit.audit_json;
  if (!shelfAudit) {
    return (
      <div className="mx-auto max-w-2xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
        This audit is marked complete but returned no data. Please treat this result as unavailable rather than retrying
        automatically.
      </div>
    );
  }

  const summary = shelfAudit.confidence_summary;
  // Indexed before filtering so review controls can reference a stable
  // "products_observed[N]" path back into the original array.
  const indexedProducts = shelfAudit.products_observed.map((product, index) => ({ product, index }));
  const detectedProducts = indexedProducts.filter(({ product }) => product.overall_confidence >= 0.5);
  const reviewProducts = indexedProducts.filter(({ product }) => product.overall_confidence < 0.5);
  const shareEntries = Object.entries(shelfAudit.share_of_shelf.by_brand).sort((a, b) => b[1] - a[1]);
  const frameQualityRecords = shelfAudit.pipeline_trace?.frame_quality_records ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Shelf Audit Result</h1>
        <Link to="/" className="text-sm font-medium text-blue-700 hover:underline">
          New Audit
        </Link>
      </div>

      {/* Audit Summary Card */}
      <section className="grid grid-cols-1 gap-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm sm:grid-cols-[auto_1fr]">
        <div className="h-40 w-full overflow-hidden rounded-lg bg-gray-100 sm:w-56">
          {audit.media_type === "image" ? (
            <img src={resolveMediaUrl(audit.media_url)} alt="analyzed shelf" className="h-full w-full object-cover" />
          ) : (
            <video src={resolveMediaUrl(audit.media_url)} controls className="h-full w-full object-cover" />
          )}
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Store</p>
            <p className="mt-0.5 font-semibold text-gray-900">{storeName}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Audit ID</p>
            <p className="mt-0.5 truncate font-mono text-xs text-gray-700" title={audit.id}>
              {audit.id}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Created</p>
            <p className="mt-0.5 text-sm text-gray-900">{formatDateTime(audit.created_at)}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Overall confidence</p>
            <div className="mt-1">
              <ConfidenceBadge score={summary.overall_confidence} />
            </div>
          </div>
          <div className="col-span-2 sm:col-span-4">
            <p className="text-xs text-gray-500">
              {summary.high_count} high &middot; {summary.medium_count} medium &middot; {summary.low_count} low &middot;{" "}
              {summary.frames_analyzed} frame(s) analyzed
            </p>
            {summary.warnings.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
                {summary.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {/* Detected Products */}
      <SectionCard title={`Detected Products (${detectedProducts.length})`} subtitle="Items identified with sufficient confidence to trust at a glance.">
        {detectedProducts.length === 0 ? (
          <EmptyNote>No products were identified with confidence &ge; 50%.</EmptyNote>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {detectedProducts.map(({ product, index }) => (
              <ProductCard product={product} key={index} />
            ))}
          </div>
        )}
      </SectionCard>

      {/* Needs Review */}
      <SectionCard
        title={`Needs Review (${reviewProducts.length})`}
        subtitle="Low-confidence detections the system refused to guess on. Confirm, correct, or reject each one."
      >
        {reviewProducts.length === 0 ? (
          <EmptyNote>Nothing flagged for review - every detected item met the confidence bar.</EmptyNote>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {reviewProducts.map(({ product, index }) => (
              <ProductCard product={product} variant="review" auditId={audit.id} index={index} key={index} />
            ))}
          </div>
        )}
      </SectionCard>

      {/* Analyzed Media */}
      <SectionCard
        title="Analyzed Media"
        subtitle="Every frame the pipeline evaluated - used for vision analysis or rejected, and why."
      >
        <FrameGallery records={frameQualityRecords} />
      </SectionCard>

      {/* Out of stock */}
      <SectionCard title={`Out-of-Stock Signals (${shelfAudit.out_of_stock_signals.length})`} subtitle="Possible gaps or missing SKUs on the shelf.">
        {shelfAudit.out_of_stock_signals.length === 0 ? (
          <EmptyNote>No out-of-stock signals detected.</EmptyNote>
        ) : (
          <div className="space-y-3">
            {shelfAudit.out_of_stock_signals.map((s, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <FieldValue field={s.location} label="Location" />
                  <ConfidenceBadge score={s.overall_confidence} size="sm" />
                </div>
                <div className="mt-2">
                  <FieldValue field={s.likely_product} label="Likely product" />
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* Competitor Activity & Promotions */}
      <SectionCard
        title="Competitor Activity & Promotions"
        subtitle="Signage, displays, and price reads observed on shelf - the system doesn't track a single 'home brand', so this surfaces all shelf marketing/pricing activity for the field rep to interpret."
      >
        {shelfAudit.promotions.length === 0 && shelfAudit.pricing_reads.length === 0 ? (
          <EmptyNote>No promotions or price reads detected.</EmptyNote>
        ) : (
          <div className="space-y-3">
            {shelfAudit.promotions.map((p, i) => (
              <div key={`promo-${i}`} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <FieldValue field={p.promo_type} label="Type" />
                  <ConfidenceBadge score={p.overall_confidence} size="sm" />
                </div>
                <div className="mt-2">
                  <FieldValue field={p.text_detected} label="Text detected" />
                </div>
                <div className="mt-2">
                  <FieldValue field={p.associated_product} label="Associated product" />
                </div>
              </div>
            ))}
            {shelfAudit.pricing_reads.map((p, i) => (
              <div key={`price-${i}`} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <FieldValue field={p.product} label="Product" />
                  <ConfidenceBadge score={p.overall_confidence} size="sm" />
                </div>
                <div className="mt-2">
                  <FieldValue field={p.price} label="Price read" />
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* Shelf Intelligence */}
      <SectionCard title="Shelf Intelligence" subtitle="Share of shelf across all brands identified (including competitors), shelf layout, and compliance.">
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Share of Shelf</h3>
            <p className="text-xs text-gray-500">{shelfAudit.share_of_shelf.reason}</p>
            {shareEntries.length === 0 ? (
              <EmptyNote>No share-of-shelf could be computed.</EmptyNote>
            ) : (
              <div className="mt-2 space-y-1.5">
                {shareEntries.map(([brand, pct]) => (
                  <div key={brand} className="flex items-center gap-3">
                    <span className="w-28 shrink-0 truncate text-sm text-gray-700">{brand}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-10 shrink-0 text-right text-xs text-gray-500">{pct}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-800">Shelf Positions ({shelfAudit.shelf_positions.length})</h3>
            {shelfAudit.shelf_positions.length === 0 ? (
              <EmptyNote>No distinct shelf positions were described.</EmptyNote>
            ) : (
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {shelfAudit.shelf_positions.map((p, i) => (
                  <div key={i} className="rounded-lg border border-gray-200 p-3">
                    <FieldValue field={p.level} label="Level" />
                    <div className="mt-2">
                      <FieldValue field={p.description} label="Description" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-800">Compliance Flags ({shelfAudit.compliance_flags.length})</h3>
            {shelfAudit.compliance_flags.length === 0 ? (
              <EmptyNote>No compliance issues detected.</EmptyNote>
            ) : (
              <div className="mt-2 space-y-2">
                {shelfAudit.compliance_flags.map((f, i) => (
                  <div key={i} className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <FieldValue field={f.issue_type} label="Issue" />
                    <div className="mt-2">
                      <FieldValue field={f.description} label="Description" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </SectionCard>

      {shelfAudit.notes && (
        <SectionCard title="Notes">
          <p className="text-sm text-gray-700">{shelfAudit.notes}</p>
        </SectionCard>
      )}

      <AuditTrace audit={shelfAudit} />
    </div>
  );
}
