import { request } from "./client";
import type { VisionProviderName, VisionProviderStatus } from "../types/audit";

/** Developer/demo-only control panel API - see types/audit.ts and
 * backend/api/settings.py for why this is intentionally separate from the
 * field-representative upload/audit flow. */
export const settingsApi = {
  getVisionProvider: () => request<VisionProviderStatus>("/api/settings/vision-provider"),

  setVisionProvider: (provider: VisionProviderName) =>
    request<VisionProviderStatus>("/api/settings/vision-provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider }),
    }),
};
