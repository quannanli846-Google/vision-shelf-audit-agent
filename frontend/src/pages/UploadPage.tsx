import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { accountsApi } from "../api/accounts";
import { auditsApi } from "../api/audits";
import { ApiError } from "../api/client";
import { UploadZone } from "../components/UploadZone";
import type { Account } from "../types/audit";

export function UploadPage() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountId, setAccountId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const loadAccounts = () => {
    setAccountsLoading(true);
    setAccountsError(null);
    accountsApi
      .list()
      .then((accts) => {
        setAccounts(accts);
        if (accts.length > 0) setAccountId(accts[0].id);
      })
      .catch((err: unknown) => setAccountsError(err instanceof Error ? err.message : "Could not load accounts"))
      .finally(() => setAccountsLoading(false));
  };

  useEffect(loadAccounts, []);

  const selectedAccount = accounts.find((a) => a.id === accountId) ?? null;
  const canSubmit = Boolean(accountId) && Boolean(file) && !submitting;

  const handleSubmit = async () => {
    if (!accountId || !file) return;
    setSubmitError(null);
    setSubmitting(true);
    try {
      const result = await auditsApi.create(accountId, file);
      navigate(`/audits/${result.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.status === 0 ? err.message : `Upload failed (${err.status}): ${err.message}`);
      } else {
        setSubmitError(err instanceof Error ? err.message : "Upload failed for an unknown reason");
      }
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">New Audit</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload a shelf photo or walkthrough video. The AI pipeline will identify products, gauge confidence, and flag
          anything it can't verify - it never guesses.
        </p>
      </div>

      <div className="space-y-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">Store / Account</label>
          {accountsError ? (
            <div className="flex items-center justify-between rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200">
              <span>{accountsError}</span>
              <button type="button" onClick={loadAccounts} className="font-semibold underline hover:no-underline">
                Retry
              </button>
            </div>
          ) : (
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              disabled={accountsLoading || accounts.length === 0}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
            >
              {accountsLoading && <option>Loading accounts...</option>}
              {!accountsLoading && accounts.length === 0 && <option>No accounts available</option>}
              {accounts.map((acct) => (
                <option key={acct.id} value={acct.id}>
                  {acct.store_name}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">Shelf media</label>
          <UploadZone file={file} onFileChange={setFile} />
        </div>

        {(selectedAccount || file) && (
          <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm">
            {selectedAccount && (
              <p>
                <span className="text-gray-500">Selected account: </span>
                <span className="font-medium text-gray-900">{selectedAccount.store_name}</span>
              </p>
            )}
            {file && (
              <p>
                <span className="text-gray-500">Media: </span>
                <span className="font-medium text-gray-900">{file.name}</span>
              </p>
            )}
          </div>
        )}

        {submitError && (
          <div className="flex items-center justify-between rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200">
            <span>{submitError}</span>
            <button type="button" onClick={handleSubmit} className="shrink-0 font-semibold underline hover:no-underline">
              Retry
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {submitting && (
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-90" fill="currentColor" d="M12 2a10 10 0 0 1 10 10h-4a6 6 0 0 0-6-6V2Z" />
            </svg>
          )}
          {submitting ? "Uploading..." : "Analyze Shelf"}
        </button>
      </div>
    </div>
  );
}
