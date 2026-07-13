# Photo / Receipt Entry (Transaction-Entry Upgrade — Phase 1)

**Date:** 2026-07-13
**Status:** Approved — ready to build

## Problem

Recording a transaction today means typing it (structured form, natural-language,
or Excel). A shopkeeper holding a paper bill still has to read it and re-key every
field. The fastest possible entry is: **snap the bill → the form is filled → save.**

The whole photo→journal pipeline already exists (`bookkeeper.service.ingest`,
`parseTransactionFromImage`). Only the vision seam is stubbed: `callAIVision`
throws because DeepSeek (our text LLM) has no image input. We have a
`GEMINI_API_KEY` (local + Vercel). This phase wires Gemini vision into the
existing pipeline and adds one "Snap a bill" control on the Record sheet.

## Design choice (confirmed)

The photo **fills the structured form for an immediate save** — the same
autofill path the natural-language tab already uses (`onParsed` →
`nlResultToFormValues` → structured form). Fewest taps: snap → glance → Save.
No separate confirm screen, no auto-post. The user always sees the filled form
and taps Save (their one deliberate confirmation).

## Architecture

Single accounting pipeline — the image path reuses the text path's normalization,
intent resolution, journal generation, validation, confidence, and preview
enrichment. Only the extraction provider differs.

```
Snap a bill (Record sheet / NLTab)
  → fileToImage() downscale → base64 JPEG          [client]
  → POST /transactions/nl/image { image, mimeType } [new endpoint]
  → parserService.parseTransactionFromImage(...)    [existing]
       → callAIVision(base64, mime, accounts, items) [REWRITTEN → Gemini]
            → gemini.service.callVision(...)          [NEW]
       → _finishParse(...)  ← SAME as text path
  → buildNlPreviewResponse(...)  ← SHARED with /nl (extracted)
  → preview JSON  → nlResultToFormValues → form autofilled  [client]
```

### Components

1. **`services/gemini.service.js` (NEW)** — Gemini REST vision client, mirrors
   `deepseek.service.js`: `requireApiKey()` (GEMINI_API_KEY), `fetchWithTimeout`,
   retry on 429/503/overload. Exports `callVision(imageBase64, mimeType, {system, user, ...})`
   returning `{ text, provider: 'gemini' }`. Uses
   `POST {BASE}/models/{GEMINI_MODEL}:generateContent?key=…` with
   `contents:[{parts:[{text}, {inline_data:{mime_type,data}}]}]` and
   `generationConfig.responseMimeType = 'application/json'`. Model default
   `gemini-2.5-flash` (env `GEMINI_MODEL`).

2. **`callAIVision` (REWRITTEN)** — builds the SAME `buildSystemPrompt(accounts,
   inventoryItems)` schema, adds a short vision instruction as the user part,
   calls `gemini.callVision`, `extractJSON`s the reply → the identical
   `rawExtraction` shape the text path produces. If `GEMINI_API_KEY` is missing,
   throws the existing catchable `isVisionUnsupported` error so callers degrade
   gracefully. `parseTransactionFromImage` threads `opts.inventoryItems` into it.

3. **`buildNlPreviewResponse(...)` (EXTRACTED)** — the ~160 lines of preview
   enrichment currently inline in `processNaturalLanguage` (learned mapping,
   account resolution, journal-line resolution, guardrail, AI decision ledger,
   opt-in auto-post) move into one shared helper. Both `/nl` and `/nl/image`
   call it, guaranteeing one behaviour. Returns either a created/auto-posted
   response or a plain preview.

4. **`POST /transactions/nl/image` (NEW)** — same RBAC/guards as `/nl`. Body:
   `{ image: base64, mimeType, attempt? }` (JSON; app json limit is 10mb).
   Loads accounts + inventory, calls `parseTransactionFromImage`, then
   `buildNlPreviewResponse`. `promptVersion: 'nl-image-v1'`, model `gemini-vision`.

5. **Frontend "Snap a bill"** — a photo control in `NLTab`. Reuses a shared
   `fileToImage` util (extracted from CommandCenterPage). On pick → upload via
   new `useNLImagePreview` → on result `onParsed(nlResultToFormValues(result, ''))`
   → structured form fills → user taps Save. Same clarification/auto-post
   handling as text (the response shape is identical).

## Error handling

- Missing key / vision failure → `isVisionUnsupported`/parse error → toast
  "Couldn't read that photo — type it instead", form stays open. Never blocks
  manual entry.
- Non-image file → client rejects before upload.
- Gemini overload (429/503) → retried, then a clear busy message.
- Accounting correctness is untouched: the image only produces a *suggestion*;
  it flows through the same validation + the user confirms by saving.

## Testing

- `gemini.service` unit tests (mocked `fetch`): success parse, missing key throws,
  429 retry then success, request body shape (inline_data + JSON mime).
- `callAIVision` contract test (mocked gemini): returns the rawExtraction shape;
  missing key → `isVisionUnsupported`.
- Existing `parseTransactionFromImage` / `bookkeeper.ingest` tests must stay green
  (now exercising the real seam via mock).
- Frontend: `naturalLanguageImageParse` service + `useNLImagePreview` smoke; build.
- Live: one real receipt photo end-to-end (now possible — key is local).

## Out of scope (later phases)

Voice, bank/wallet SMS paste, quick-pick recents, per-party memory, duplicate
detection, offline PWA queue, split entry. Sequenced after this ships.
