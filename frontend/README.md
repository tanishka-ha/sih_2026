# VERITY — ScholarGuard Frontend

SIH 2026 frontend prototype for the explainable scholarship application verification system.

## What this prototype demonstrates

- Review queue ranked by human attention
- Application-level bundle review
- Evidence-backed findings with document-region highlighting
- Cross-document and cross-application comparison
- OCR quality / re-upload handling
- Forensic signal summary (ELA, EXIF, font alignment, copy-move)
- Human-in-the-loop decision actions: clear, request correction, escalate
- SHA-256 chained audit events generated in-browser
- Machine-readable `results.json` export
- Measured extraction metrics from the SIH presentation
- Interchangeable bright / dark theme
- Responsive layout for laptops and projectors

## Run locally

```bash
python3 -m http.server 5173
```

Open `http://localhost:5173`.

## Backend hand-off

The current build intentionally uses the existing controlled demo dataset in `data.js`. When the FastAPI backend is ready, replace the mock application objects with API responses and keep the same UI data contract:

```text
Verification Engine → FastAPI → JSON → ScholarGuard Dashboard → Human Decision
```

The coordinate contract for evidence boxes remains normalized to `0..1` relative to the rendered page, linked to a finding by `flagId`.

## Frontend scope
This prototype is intentionally limited to the reviewer-facing dashboard. It does not implement OCR, forensics, or server-side verification. Demo data is local and deterministic. Browser upload supports PDF/PNG/JPEG selection and previews image sources locally; PDFs are preserved as source files for the verification service. The UI is prepared for backend integration without inventing verification results.

### Review queue UI updates
- Explicit HIGH / MEDIUM / CLEAR / RE-UPLOAD severity filters.
- Severity and review state are separated visually.
- Cross-application match is surfaced as a reviewer-facing work item, not a fraud verdict.
- Governance includes human decision required and no authenticity claim.
- Dark / Bright theme toggle is persisted locally.
- Hover/focus glows provide live interaction feedback without adding non-functional product features.

## Upload / backend contract

The New application flow accepts multiple `.pdf`, `.png`, `.jpg`, and `.jpeg` files. Image uploads are previewed locally in the document viewer; PDFs remain source files for the backend. The frontend does not claim a verification result until the verification service returns one.

When the team backend is ready, set `window.SCHOLARGUARD_API_BASE` before loading `app.js`. The frontend then POSTs a `multipart/form-data` request to `/api/applications/verify` with `application_id` and repeated `documents` file fields. A compatible JSON response can provide `band`, `status`, `headline`, `readable`, `documents`, and `flags`; the existing evidence-box coordinate contract remains normalized to `0..1` with `flagId` linking regions to findings. If no API base is configured, uploads remain local and explicitly show an "awaiting verification" state.
