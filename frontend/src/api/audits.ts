import { request } from "./client";
import type { Audit, AuditCreateResponse, AuditFeedback, AuditFeedbackCreate, AuditListItem, AuditTraceResponse } from "../types/audit";

export const auditsApi = {
  create: (accountId: string, file: File) => {
    const form = new FormData();
    form.append("account_id", accountId);
    form.append("file", file);
    return request<AuditCreateResponse>("/api/audits", { method: "POST", body: form });
  },

  get: (id: string) => request<Audit>(`/api/audits/${id}`),

  getTrace: (id: string) => request<AuditTraceResponse>(`/api/audits/${id}/trace`),

  list: (accountId?: string) => request<AuditListItem[]>(`/api/audits${accountId ? `?account_id=${accountId}` : ""}`),

  submitFeedback: (auditId: string, feedback: AuditFeedbackCreate) =>
    request<AuditFeedback>(`/api/audits/${auditId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback),
    }),

  listFeedback: (auditId: string) => request<AuditFeedback[]>(`/api/audits/${auditId}/feedback`),
};
