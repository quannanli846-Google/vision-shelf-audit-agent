import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { auditsApi } from "../api/audits";
import { ApiError } from "../api/client";
import type { AuditListItem, AuditStatus } from "../types/audit";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { formatDateTime, titleCase } from "../lib/format";

const STATUS_STYLES: Record<AuditStatus, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  processing: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
};

export function HistoryPage() {
  const [audits, setAudits] = useState<AuditListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    auditsApi
      .list()
      .then((items) =>
        setAudits([...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())),
      )
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load audit history"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Audit History</h1>
          <p className="mt-1 text-sm text-gray-500">Every shelf audit submitted so far, most recent first.</p>
        </div>
        <Link
          to="/"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New Audit
        </Link>
      </div>

      {error && (
        <div className="mb-4 flex items-center justify-between rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200">
          <span>{error}</span>
          <button type="button" onClick={load} className="font-semibold underline hover:no-underline">
            Retry
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-200 bg-gray-50 text-xs font-medium uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">Store</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Media type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  Loading audit history...
                </td>
              </tr>
            )}
            {!loading && audits.length === 0 && !error && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No audits yet. Submit your first shelf photo or video from New Audit.
                </td>
              </tr>
            )}
            {audits.map((a) => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{a.store_name}</td>
                <td className="px-4 py-3 text-gray-600">{formatDateTime(a.created_at)}</td>
                <td className="px-4 py-3 capitalize text-gray-600">{a.media_type}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[a.status]}`}>
                    {titleCase(a.status)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {a.overall_confidence !== null ? <ConfidenceBadge score={a.overall_confidence} size="sm" /> : <span className="text-gray-400">-</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link to={`/audits/${a.id}`} className="font-semibold text-blue-700 hover:underline">
                    View audit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
