// Base fetch wrapper shared by every domain-specific API module
// (accounts.ts, audits.ts). Nothing here knows about accounts/audits -
// keeping it generic is what makes the domain modules easy to test/mock
// independently.

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    // A thrown fetch (not a non-2xx response) means the server was
    // unreachable entirely - surface that distinctly so the UI never
    // pretends a "missing API response" is the same as a real failure.
    throw new ApiError("Could not reach the Vision AI Shelf Audit API. Is the backend running?", 0);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore - fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<T>;
}

export function resolveMediaUrl(mediaUrl: string): string {
  return mediaUrl.startsWith("http") ? mediaUrl : `${API_BASE_URL}${mediaUrl}`;
}
