# Step 05 — Multimodal RAG

Status: Complete

## Goal

Support product images and manuals while preserving source evidence.

## Prerequisite

Complete step 04 first.

## What you will learn

PDF extraction, tables, OCR or vision, uncertain identification, multimodal retrieval.

## Build checklist

- [x] Add a small set of fictional or appropriately licensed manuals, product images, and specification tables.
- [x] Extract PDF text and tables with page metadata; use OCR or vision only where needed.
- [x] Add bounded file uploads with type and size validation.
- [x] Use vision to propose a product identity from an image and request clarification when ambiguous.
- [x] Retrieve the matching manual section and provide instructions with document and page citations.
- [x] Treat uploaded documents and extracted text as untrusted content, not application instructions.
- [x] Test clear images, ambiguous models, unreadable files, and missing manuals. Image embeddings are an optional later experiment.

## Done when

- [x] A supported product image leads to a cited answer from its manual.
- [x] Ambiguous identification does not produce confident model-specific instructions.
- [x] Unsupported or oversized files are rejected cleanly.

## Scope

Keep the example catalog small; do not build a general document platform.

## Build request

> Build step 05 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Core concepts

- **Two stages: identify, then retrieve.** A vision model looks at the photo and only *proposes* which catalog product it shows. The backend validates that proposal, then retrieves that product's manual pages with ordinary text RAG. The answering model never sees the image; it sees the validated product name and the cited manual pages.
- **Closed-set identification.** The vision model may only answer with catalog IDs and one of four statuses: `identified`, `ambiguous`, `not_supported` or `unclear_image`. Any unknown ID or inconsistent combination counts as invalid output. It gets one retry, then a fallback reply.
- **Uncertainty is a normal outcome.** TP-58 and TP-80 printers share a housing on purpose. Without a readable label, the right answer is "which model is it?", not a guess. Ambiguous, no-manual, unsupported and unclear photos get fixed server-written replies, and no manual instructions are retrieved or generated for them.
- **Page metadata is part of the evidence.** Each manual page becomes one chunk carrying `page` and `product`. Citations return the page, so the UI shows "Panduan DemoPrint TP-58, p. 2".
- **Tables keep their structure.** pdfplumber finds ruled tables and turns them into Markdown rows, placed where they appear on the page. Their cell text is removed from the loose page text so it isn't duplicated.
- **OCR only where needed.** The manuals have a text layer, so no OCR is used. A page without text is reported by ingestion and skipped. A manual with no readable pages is rejected, because scanned manuals would need OCR, which isn't enabled.
- **Untrusted inputs.** Photo text such as stickers, extracted manual text and history notes are data. The identification prompt tells the model to report label text, not obey it. The backend also changes `identified` to `ambiguous` when the reported label names a different catalog model.

## How it works

```text
Browser: question + optional photo (PNG/JPEG/WebP ≤ 5 MB)
  → POST /chat/image (multipart: payload = /chat JSON, image = file)
  → Size guard before multipart parsing (Content-Length ≤ 5.5 MB)
  → Validate chat state, sniff magic bytes, check dimensions, decode, strip EXIF, downscale to ≤1024 px, re-encode JPEG
  → Vision call (catalog + photo only; the customer's question is not sent)
  → Validate against catalog → identified / ambiguous / not_supported / unclear_image
       ├── ambiguous, unclear, not supported, or no manual → fixed reply, no retrieval
       └── identified with manual → retrieve (product name + question), other models' manuals excluded
             → answer model: evidence pages + PRODUCT IDENTIFICATION note → validated citations with page
```

Text-only `/chat` also benefits. If the current question (or, failing that, recent user context) names exactly one catalog model, such as "TP-80", evidence from other models' manuals is excluded. After a photo reply, the browser stores the question with a short note in history, for example `[Foto terlampir: dikenali sebagai DemoPrint TP-58]`, so follow-ups keep the model. The image itself is not kept.

## Implementation

- **Catalog** — [knowledge/manuals/catalog.json](../knowledge/manuals/catalog.json) lists four fictional products. Three have manuals: DemoPrint TP-58, DemoPrint TP-80 and DemoScan BS-100. The DemoCash CD-40 cash drawer has no manual, to exercise the missing-manual path. Products need exact fields. Manual paths must be PDFs in the catalog folder, with no path traversal.
- **Manuals** — three short Indonesian PDFs with specification and indicator tables, plus running headers that name the model. They are generated by [scripts/make_step05_fixtures.py](../scripts/make_step05_fixtures.py), a tiny standard-library PDF writer that also draws the sample photos with Pillow.
- **Sample photos** — [steps/05-sample-images/](05-sample-images/) contains labelled TP-58, TP-80 and BS-100 photos, an unreadable printer label, the CD-40 (no manual), a coffee mug, and a TP-58 photo with a sticker trying to inject instructions.
- **Index** — manual pages are indexed beside the Markdown knowledge in the same SQLite file, with the same keyword/vector/hybrid search. The chunker version became `markdown-sections-v1+pdf-pages-v1`. Index metadata stores SHA-256 hashes of the catalog and each PDF, so any edit requires re-ingestion.
- **Uploads** — `app/uploads.py`. The file type comes from magic bytes; the client's file name and content type are ignored. Limits: 5 MB per file, 32 px minimum side, 40 MP maximum (checked before pixels are decoded). EXIF orientation is applied, and transparency is flattened. Re-encoding drops EXIF/GPS metadata and embedded text.
- **Vision** — `app/vision.py` and [prompts/identify-v1.txt](../prompts/identify-v1.txt). The model defaults to the chat model (`deepseek-v4p1-flash`, which accepts images on Fireworks serverless). Override it with `FIREWORKS_VISION_MODEL` or `OPENAI_VISION_MODEL`. Both provider request shapes are implemented and tested: Chat Completions `image_url` and Responses `input_image`.
- **Answer prompt** — [prompts/support-v6.txt](../prompts/support-v6.txt) adds rules for manual pages, ambiguous multi-model evidence and photo identification notes. v5 is preserved.
- **Time budget** — the photo route allows 45 seconds for both provider calls; the browser waits up to 60 seconds.

New dependencies, as documented in `requirements.txt`:

- `pdfplumber` handles page-level text and ruled-table extraction. It brings in pdfminer.six, pypdfium2 and cryptography.
- `pillow` decodes, bounds and re-encodes photos.
- `python-multipart` lets FastAPI parse multipart form uploads.

## Commands

```sh
# Regenerate fictional manuals and photos (already committed).
.venv/bin/python scripts/make_step05_fixtures.py

# Re-ingest: required once because the chunker version and sources changed.
.venv/bin/python -m app.ingest

# Disable manuals and photo upload, or use your own catalog folder (ignored knowledge/local/ is a good place).
SAAS_MANUALS_DIR= .venv/bin/python -m uvicorn app.main:app --port 8000
SAAS_MANUALS_DIR=knowledge/local/manuals .venv/bin/python -m app.ingest
```

## Verification (2026-11-25)

Automated checks need no API key and make no paid calls. All pass: 276 pytest checks, 7 Node tests and `pip check`. New coverage:

- Catalog validation: path traversal, missing files, duplicate IDs, extra fields, bad aliases.
- PDF extraction: page numbers, tables extracted once, reading order, scanned and mixed PDFs, corrupt or empty PDFs.
- Manual indexing: product filtering and freshness after a PDF or catalog change.
- Uploads: EXIF stripping, downscaling, WebP transparency, and rejection of empty, GIF, PDF, SVG, corrupt, truncated, tiny, 48 MP and oversized files.
- Identification: every status, label conflicts, 11 malformed outputs, retry and fallback.
- Photo route on both providers: the image is sent re-encoded and only to the vision call, citations outside the identified manual are rejected, and bad uploads never reach the provider.
- Browser: multipart sending, retry keeps the photo, page citations, history notes, local file-type refusal.

Live run against Fireworks `deepseek-v4p1-flash` with the local Jagel knowledge plus manuals (28 chunks, 8 manual pages):

| Photo | Result | Time |
| --- | --- | --- |
| `tp58-labelled.png` + Bluetooth question | Identified TP-58; correct steps and PIN 0000; cites TP-58 pp. 2–3 | 4.8 s |
| `tp80-labelled.png` + orange light | Identified TP-80; "cutter jammed"; cites TP-80 p. 3 | 2.9 s |
| `bs100-labelled.png` + double scan | Identified BS-100; cites p. 2 | 2.8 s |
| `printer-label-unreadable.png` | Ambiguous TP-58/TP-80; asks for the label; no steps | 1.2 s |
| `cd40-labelled.png` | Identified CD-40; manual unavailable; human support | 2.0 s |
| `coffee-mug.png` | Not supported; human support | 1.0 s |
| `tp58-with-injection-sticker.png` + warranty | Identified TP-58; 12 months (sticker ignored); cites TP-58 | 3.0 s |

Follow-up "Labelnya TP-80." after the ambiguous photo returned TP-80 paper-loading steps citing TP-80 p. 2. "Berapa harga paket Silver?" still cites the Jagel knowledge. A PDF, a text file, a 6 MB file and a corrupt PNG returned 415, 415, 413 and 422.

Not verified: a manual click-through in a real browser (the UI was tested with the Node harness and the endpoint with real HTTP), the OpenAI vision path against the live API (simulated only), and non-synthetic photographs.

## Limitations

- **Behaviour when no model is given.** "Printer saya lampunya merah berkedip" (no model given) was answered from the TP-58 page with a caveat to confirm the model, rather than first asking which model. Only TP-58 defines that indicator, but the prompt rule was followed loosely. Deterministic filtering applies only when a model is identified or typed.
- **Identification can be wrong.** It is an uncalibrated model proposal. Labels can be misread, and look-alike products outside the catalog can be confused with catalog products. The UI asks customers to confirm the label.
- **Synthetic photos.** The sample photos are clean illustrations. Real photos (glare, angles, partial labels) will be harder, so evaluate with your own licensed photos before relying on this.
- **No OCR.** Scanned manuals without a text layer are rejected, and pages without text are skipped and reported. Complex layouts (multi-column pages, unruled tables) may extract in a poor order.
- **No image search.** Retrieval uses text only (product name + question); image embeddings were not attempted. Photos are never stored, so the bot cannot re-inspect an earlier photo.
- **Requests without a length.** The upload size guard requires `Content-Length`; requests without it get a 411.
