import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { settingsApi } from "../api/settings";
import type { VisionProviderName, VisionProviderStatus } from "../types/audit";

/** Which providers this control exposes. Both real providers use the same
 * OpenAI-compatible chat-completions shape (`vision/providers/openai.py` and
 * `vision/providers/groq.py`), so there's no reason to hide Groq from this
 * switch just because the original ask only named OpenAI - anyone with a
 * Groq key (no OpenAI account needed) should be able to see real inference
 * the same way. */
const SELECTABLE_PROVIDERS: VisionProviderName[] = ["openai", "groq", "mock"];

/** Developer/demo-only control, NOT a field-representative feature.
 *
 * Lets whoever is running a demo flip the active `VisionClient` between
 * Mock Vision and a real provider (OpenAI or Groq) without restarting the
 * backend. The frontend only ever sends the chosen provider name to
 * `POST /api/settings/vision-provider` - it never constructs a vision
 * client itself; the backend remains the sole owner of provider creation
 * (see `backend/vision/client.py` and `backend/api/settings.py`).
 *
 * Visually set apart (dashed amber border + "DEV" badge) so it's never
 * mistaken for part of the field-rep upload/audit workflow.
 */
export function VisionProviderSwitch() {
  const [status, setStatus] = useState<VisionProviderStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    settingsApi
      .getVisionProvider()
      .then(setStatus)
      .catch(() => {
        // Dev tool only - if the backend is unreachable, fail quietly here
        // rather than surfacing an error banner on top of the real
        // field-rep workflow. The rest of the app will report that
        // separately when it actually tries to talk to the API.
      });
  }, []);

  async function handleChange(provider: VisionProviderName) {
    if (!status || provider === status.active_provider) return;
    setPending(true);
    setError(null);
    try {
      const updated = await settingsApi.setVisionProvider(provider);
      setStatus(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to switch vision provider");
    } finally {
      setPending(false);
    }
  }

  if (!status) return null;

  const options = status.options.filter((o) => SELECTABLE_PROVIDERS.includes(o.provider));

  return (
    <div className="flex flex-col gap-1">
      <div
        className="flex items-center gap-2 rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-1.5"
        title="Developer control - switches the active vision provider for all subsequent audits. Not a field-representative feature; production deployments configure this via the VISION_PROVIDER environment variable instead (see README)."
      >
        <span className="inline-flex items-center rounded-full bg-amber-200 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
          Dev
        </span>
        <div className="flex flex-col leading-tight">
          <span className="text-[11px] font-medium text-amber-900">Vision Engine: {status.label}</span>
          <span className="text-[10px] text-amber-700">Status: {status.mode_label}</span>
        </div>
        <select
          value={status.active_provider}
          disabled={pending}
          onChange={(e) => handleChange(e.target.value as VisionProviderName)}
          className="rounded border border-amber-300 bg-white px-1.5 py-1 text-[11px] text-amber-900 disabled:opacity-50"
          aria-label="Vision provider (developer control)"
        >
          {options.map((o) => (
            <option key={o.provider} value={o.provider} disabled={!o.available}>
              {o.label} ({o.provider === "mock" ? "Development" : "Real"}){!o.available ? " \u2013 unavailable" : ""}
            </option>
          ))}
        </select>
      </div>
      {error && <span className="text-[10px] text-red-600">{error}</span>}
    </div>
  );
}
