# Step 03 — First text RAG

Status: Not started

## Goal

Answer policy and product questions using a small fictional knowledge base.

## Prerequisite

Complete step 02 first.

## What you will learn

Ingestion, chunking, embeddings, similarity search, grounding, citations.

## Build checklist

- [ ] Create knowledge files for returns, shipping, warranty, payment, membership, and a few fictional products.
- [ ] Define consistent policy fixtures: unopened items within 30 days, opened electronics within 14 days, and no returns for final-sale items. State when the return clock starts.
- [ ] Choose a simple local vector store and an embedding model; document the choices.
- [ ] Build a repeatable ingestion command that chunks documents and saves stable chunk IDs, source paths, and document versions.
- [ ] Retrieve relevant chunks for a question and construct a bounded context for the LLM.
- [ ] Require answers grounded in the retrieved context with source citations. Abstain when the sources do not answer the question.
- [ ] Retain representative questions with expected sources for later comparisons.

## Done when

- [ ] Opened-headphone questions retrieve and cite the correct policy.
- [ ] Unsupported questions produce an honest fallback.
- [ ] Re-ingestion does not duplicate chunks and updates changed documents.

## Scope

Use text documents only; customer order data belongs in controlled tools later.

## Build request

> Build step 03 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
