# 5-minute demo script

A walkthrough for presenting this prototype. Everything below runs in mock
mode - no API keys needed.

## Before you start (off-camera)

```bash
# Terminal 1
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Check `http://localhost:8000/api/health` once - you should see
`"vision_provider": "mock"` and `"supabase_configured": false`. Worth
calling out: the whole pipeline runs with zero external credentials, and
switching to real GPT-4o vision (or Groq's Llama-4-Scout) or a real
Supabase project is a pure env-var change - `OPENAI_API_KEY`, `GROQ_API_KEY`,
or `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`. No code changes, because
`vision/client.py`'s provider factory is the only thing that knows which
backend is active.

Have ready:
- One shelf photo (any beverage shelf, or `backend/sample_data/sample_shelf.jpg`)
- One short shelf video, 5-15 seconds (or `backend/sample_data/sample_shelf.mp4`)

If you have an `OPENAI_API_KEY` or `GROQ_API_KEY` handy, note the small
dashed-amber "Dev" control top-right of the header
(`Vision Engine: Mock Vision`) - it's a developer/demo switch, not a
field-rep feature. Covered in minute 2.

## Minute 1 - the problem

"A field rep walks a store, photographs or films a shelf, and we need a
structured, trustworthy audit record - not a chatbot description. The hard
part isn't calling a vision model, it's never pretending to know something
it doesn't, and proving that with a real pipeline, not just a good prompt."

Open `http://localhost:5173`. Point out the two things the brief asked for
on this page: pick a store/account, upload image or video.

## Minute 2 - image upload, live status, result

1. (Optional, if you have a key configured) Click the Dev control and
   switch Vision Engine to "OpenAI Vision (Real)" or "Groq Vision (Real)."
   Narrate: this posts the provider name to the backend, which is the only
   thing that ever constructs a `VisionClient` - a real deployment would set
   `VISION_PROVIDER` once via env var and never expose this control to end
   users. If no key is configured, leave it on Mock - real providers show up
   greyed out with the reason why.
2. Select a store, upload the sample photo, submit.
3. While it's still `processing`, point out the status updating - "analyzing
   image", then "grounding products against SKU catalog", then "calibrating
   confidence." This is the real async lifecycle: `uploaded -> processing ->
   completed`, not a fake progress bar.
4. Once complete, walk through one Detected Products card:
   - Pick a confidently-identified product (e.g. Tito's Handmade Vodka).
     Show the confidence badge, expand the factor breakdown (vision / OCR /
     catalog match / frame consistency), and read the evidence checklist -
     every line there is a reason the pipeline already computed, not
     something generated for the demo.
   - Scroll to Needs Review. Point at the product with
     `brand: Not identified`, read its reason aloud ("label obscured by
     glare"). This is the anti-hallucination behavior in action - the model
     would rather say "I don't know" than guess. Click Correct, type in the
     real brand name, submit - mention it just persisted to
     `audit_feedback` (an append-only log) without rewriting the original AI
     output above it.

## Minute 3 - confidence, share of shelf, grounding

1. Show the Confidence Summary card - overall score, high/medium/low counts,
   plain-language warnings ("1 of 3 products could not be matched to the
   reference catalog").
2. Show Share of Shelf - computed from actual counted facings, with an
   "Unidentified" bucket for facings that were counted but not named. It
   never silently drops what it can't identify.
3. Scroll to Out-of-Stock Signals and Competitor Activity & Promotions -
   same `{value, confidence, reason}` shape everywhere, including nulled
   price reads ("digits not legible at this resolution") and any competitor
   displays or price drops the model flagged.

## Minute 4 - video pipeline and reasoning trace

1. Go back, upload the sample video instead.
2. While it processes, narrate the video-specific stages: "extracting video
   frames" -> "filtering low-quality frames" -> per-frame analysis. Images
   skip straight to vision; video always goes through frame sampling and
   blur/brightness/glare/duplicate filtering first.
3. Once complete, scroll to Analyzed Media. Every sampled frame shows up,
   either "Used" with a quality score, or "Rejected" with a specific reason
   (motion blur, too dark, glare, duplicate) - this is the actual per-frame
   record the pipeline kept, not a summary written for the UI.
4. Point at the "Vision Provider: Mock Vision" badge next to the AI
   Processing Trace header - it's read live off `PipelineTrace.vision_provider`,
   set by whichever `VisionClient` was actually injected. Flip
   `VISION_PROVIDER=openai` in `.env`, restart, and re-run the same audit -
   the badge changes to "OpenAI Vision" with zero code changes, because
   nothing downstream of `vision/client.py` branches on which provider is
   active.
5. Click "Show Reasoning Trace." Point out:
   - `frames_sampled` vs. `frames_kept` - rejected frames never reach the
     vision model, which is both a cost and a quality control.
   - `frame_quality_records` - the same data powering the Analyzed Media
     gallery, with blur/brightness/quality scores per frame.
   - `raw_model_outputs` - the actual untrusted JSON returned per frame,
     before validation.
   - `validation_warnings` - anything the validator had to coerce or reject.

   This panel exists so a reviewer can see the reasoning chain, not just the
   polished result - extraction, validation, grounding, calibration, all
   inspectable.

## Minute 5 - code tour (pick 2-3)

- [`backend/models/shelf_audit.py`](../backend/models/shelf_audit.py) -
  `ExtractedField` and its null-forces-low-confidence validator, plus
  `ConfidenceBreakdown`/`ConfidenceFactors` for the per-product factors.
- [`backend/vision/client.py`](../backend/vision/client.py) +
  [`backend/vision/providers/`](../backend/vision/providers) - the provider
  abstraction: `openai.py`, `groq.py`, `mock.py` behind one `VisionClient`
  interface, chosen purely by env var.
- [`backend/vision/validator.py`](../backend/vision/validator.py) - raw
  model JSON never reaches the database directly.
- [`backend/sku/matcher.py`](../backend/sku/matcher.py) - confident match
  vs. ambiguous vs. no-match, each with an explicit reason.
- [`backend/vision/confidence.py`](../backend/vision/confidence.py) /
  [`backend/vision/extractor.py`](../backend/vision/extractor.py) - the
  cross-frame corroboration boost and the evidence-list builder.
- [`backend/video/quality_filter.py`](../backend/video/quality_filter.py) -
  blur/brightness/glare/duplicate rejection and the `FrameQualityRecord`
  kept for every sampled frame.
- [`backend/api/audits.py`](../backend/api/audits.py) - the `/feedback`
  endpoints behind the human review loop, and
  [`backend/migrations/002_audit_feedback.sql`](../backend/migrations/002_audit_feedback.sql)
  for the append-only table backing it.
- `backend/tests/` - run `pytest -v` live to show the suite passing. It
  covers provider wiring (every provider exposes a distinct `provider_name`
  shown in the trace), frame quality filtering, confidence + evidence,
  schema validation, SKU matching, and the feedback API.

Closing line: "Everything you just saw runs with no API keys and no cloud
project. Add an `OPENAI_API_KEY` (or `GROQ_API_KEY`) and Supabase
credentials, and the same code path talks to a real vision model and a real
Postgres database - zero code changes."
