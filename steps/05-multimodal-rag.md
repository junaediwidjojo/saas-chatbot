# Step 05 — Multimodal RAG

Status: Not started

## Goal

Support product images and manuals while preserving source evidence.

## Prerequisite

Complete step 04 first.

## What you will learn

PDF extraction, tables, OCR or vision, uncertain identification, multimodal retrieval.

## Build checklist

- [ ] Add a small set of fictional or appropriately licensed manuals, product images, and specification tables.
- [ ] Extract PDF text and tables with page metadata; use OCR or vision only where needed.
- [ ] Add bounded file uploads with type and size validation.
- [ ] Use vision to propose a product identity from an image and request clarification when ambiguous.
- [ ] Retrieve the matching manual section and provide instructions with document and page citations.
- [ ] Treat uploaded documents and extracted text as untrusted content, not application instructions.
- [ ] Test clear images, ambiguous models, unreadable files, and missing manuals. Image embeddings are an optional later experiment.

## Done when

- [ ] A supported product image leads to a cited answer from its manual.
- [ ] Ambiguous identification does not produce confident model-specific instructions.
- [ ] Unsupported or oversized files are rejected cleanly.

## Scope

Keep the example catalog small; do not build a general document platform.

## Build request

> Build step 05 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
