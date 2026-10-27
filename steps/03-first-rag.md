# Step 03 — First text RAG

Status: Implemented; fictional fixture and approved custom knowledge verified.

## Goal

Answer SaaS policy and product questions using relevant passages from the selected Markdown knowledge base, with verified source references.

## Prerequisite

Complete step 02 first.

## What you will learn

Ingestion, chunking, embeddings, similarity search, grounding, citations.

## Build checklist

- [x] Adapt the source material to SaaS plans, inherited features, onboarding, technical setup, payments, and support. Keep local knowledge and brand rules ignored by Git.
- [x] Keep a fictional DemoBuilder fixture with explicit plan inheritance and a narrow wrong-transfer policy; do not manufacture retail/headphone policies for the Jagel dataset.
- [x] Choose a simple local vector store and an embedding model; document the choices.
- [x] Build a repeatable ingestion command that chunks documents and saves stable chunk IDs, source paths, and document versions.
- [x] Retrieve relevant chunks for a question and construct a bounded context for the LLM.
- [x] Require answers grounded in the retrieved context with source citations. Abstain when the sources do not answer the question.
- [x] Retain representative questions with expected sources for later comparisons.

## Done when

- [x] Plan-inheritance questions retrieve and cite the relevant higher-plan rule and lower-plan feature. Verified with the fictional fixture.
- [x] Unsupported questions produce an honest fallback. Live fixture checks covered missing SLA and unsupported general subscription refunds.
- [x] Re-ingestion does not duplicate chunks and updates changed documents. Automated checks cover updates, deletions, atomic failure, and stable IDs; live unchanged re-ingestion reused all eight vectors.
- [x] Build the custom Jagel index and evaluate its representative questions after approving transmission to the embedding provider. Explicit approval received; 21 chunks indexed and representative checks passed.

## Scope

Use text documents only; customer order data belongs in controlled tools later. At the user's request, this stage uses the local Jagel source structure instead of the original consumer-retail example. Only invented examples are committed.

## Build request

> Build step 03 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Implemented on 2026-10-27 on `feat/step-03-rag`.

- Storage: standard-library SQLite, with exact cosine search over normalized vectors. No LangChain, ANN extension, or new runtime dependency.
- Embeddings: Fireworks `fireworks/qwen3-embedding-8b`, default 512 dimensions. Use the existing Fireworks key; validate dimensions and values. Queries use the Qwen retrieval instruction prefix, documents do not.
- Ingestion: `.venv/bin/python -m app.ingest`. Input follows `SAAS_KNOWLEDGE_FILE`; the default index is `.rag/knowledge.sqlite3`. Both text and vectors stay Git-ignored. Ingestion sends chunk contents to Fireworks; this is an external data transmission.
- Chunks: Markdown heading paths and parent introductions, split at paragraph boundaries with a 1,800-character body limit. IDs are stable for source path/heading/part; document versions are SHA-256 hashes. Explicit plan inheritance creates related-chunk links.
- Retrieval: embed the current question with bounded recent user context and a short summary excerpt. Select top three candidates over cosine 0.30, expand plan dependencies, and cap evidence at six passages/8,500 serialized characters. These are heuristics to evaluate, not universal settings or calibrated confidence.
- Grounding: the system prompt no longer contains the full knowledge file or assumes CloudDesk. Server-owned communication rules come from optional `SAAS_BRAND_FILE`; the UI uses `SAAS_NAME`. Retrieved passages, summaries, and chat history are data, not system instructions.
- Citations: model returns `citation_ids`; backend requires citations for factual product/pricing/policy intents and verifies IDs against this request's retrieved chunks. Backend supplies citation labels/versions, never local paths. Invalid/duplicate/missing required IDs trigger the existing bounded retry/fallback. This validates identity, not whether an answer actually follows from a source.
- Freshness: index/source/model/dimension mismatch asks for re-ingestion. Changed source is checked before retrieval. No silent full-file fallback.
- Knowledge adjustment: preserved `knowledge/local/my-saas.pre-rag.md`; removed persona instructions from factual material into ignored `prompts/local/brand.txt`; configured local display name. Corrected the outdated Maps monthly-credit claim and unrestricted-key recommendation against Google guidance. Replaced automatic Play Protect bypass advice with verification/support guidance. Remaining business facts/prices need owner review.
- Verification: backend tests cover chunking, inheritance, vector validity, context bounds, no-match retrieval, stable re-ingestion, changed/deleted documents, atomic failure, stale/missing/config-mismatched indexes, follow-up query context, citation validation, and existing memory behavior. Frontend tests cover citation text display without placing citation metadata in model history.
- Live fixture ingestion produced eight chunks; unchanged re-ingestion embedded zero and reused eight. No token/cost saving is claimed; compare with the former full-context baseline using actual measurements.
- Live fixture answers: Silver pricing cited Silver/Bronze; Gold's form feature cited Gold and Silver; free remote support cited its support section. Missing uptime SLA and general refund policy returned unknown/human-support recommendations. The real browser displayed the Gold answer and both source sections/version labels.
- Evaluation: `.venv/bin/python -m app.evaluate_retrieval` uses `03-retrieval-examples.json`. This worksheet targets the custom Jagel corpus; run after its index exists. Inspect source recall and answer correctness separately.

### Approved custom ingestion and verification

The user explicitly approved sending `knowledge/local/my-saas.md` to Fireworks for embeddings on 2026-10-27. The custom index now contains 21 chunks. Unchanged re-ingestion embedded zero and reused all 21 vectors. The knowledge, backup, brand rules, and SQLite index remain Git-ignored.

All six worksheet questions with expected source sections retrieved those sections: pricing, plan inheritance, remote support, transport setup, Firebase login, and wrong-transfer handling. The two unsupported-policy questions were assessed separately through live generated answers.

Five live custom-data answer checks passed: pricing cited its plan sources; inherited forms cited Gold plus Silver; remote support cited its support section; unsupported uptime SLA and general subscription refunds were classified as unknown with human-support recommendations. The wrong-transfer procedure was not presented as a general refund policy. These are spot checks, not a guarantee of factual accuracy.

A separate follow-up check supplied a prior user message about Gold, then asked whether “paket itu” includes forms. Retrieval and the answer resolved Gold and cited both Gold's inheritance and Silver's feature section.

The selected custom file contains 13,354 characters; these worksheet requests produced 2,214–6,166 serialized evidence characters. This measures evidence size only, not full prompt size, actual model tokens, cost, or latency. No cost-saving claim is made.

References: [Fireworks embeddings](https://docs.fireworks.ai/guides/querying-embeddings-models), [Qwen model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B), [Maps pricing](https://developers.google.com/maps/billing-and-pricing/overview), [Maps key security](https://developers.google.com/maps/api-security-best-practices).
