# Step 04 — Improve retrieval

Status: Not started

## Goal

Measure whether better retrieval actually improves answers.

## Prerequisite

Complete step 03 first.

## What you will learn

Query rewriting, BM25, hybrid search, ranking, Recall@K, quality and latency tradeoffs.

## Build checklist

- [ ] Create a fixed question set with relevant source or chunk labels, including exact product names and ambiguous warranty questions.
- [ ] Measure the vector-only baseline before changing retrieval.
- [ ] Add keyword/BM25 retrieval and a documented hybrid result-fusion method.
- [ ] Experiment with query rewriting that preserves product names and user constraints.
- [ ] Add optional reranking; use configurable candidate and final-context limits.
- [ ] Compare vector-only, keyword-only, hybrid, and hybrid plus reranking on the same dataset.
- [ ] Record Recall@K, answer quality, latency, and estimated cost; choose the simplest pipeline supported by the results.

## Done when

- [ ] A repeatable comparison report exists.
- [ ] Every returned chunk keeps its source metadata.
- [ ] The chosen configuration has measured benefits or explicitly documents why the baseline remains preferable.

## Scope

Do not assume more pipeline components always improve retrieval.

## Build request

> Build step 04 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
