# Step 04 — Improve retrieval

Status: Complete

## Goal

Measure whether better retrieval actually improves answers, then choose the simplest useful configuration.

## Prerequisite

Complete step 03 first.

## What you will learn

Query rewriting, BM25, hybrid search, reranking, Recall@K, answer evaluation, and quality/latency/cost tradeoffs.

## Build checklist

- [x] Create a fixed question set with relevant source labels, exact feature names, follow-ups, paraphrases, and unsupported policy questions.
- [x] Measure the vector-only baseline before changing retrieval.
- [x] Add BM25 keyword retrieval and document hybrid result fusion.
- [x] Experiment with query rewriting that preserves original product names and user constraints.
- [x] Add optional reranking and configurable candidate/final-context limits.
- [x] Compare vector-only, keyword-only, hybrid, hybrid plus reranking, and hybrid plus rewriting on the same dataset.
- [x] Record Recall@K, answer quality, comparable latency, and estimated cost; choose the simplest supported pipeline.

## Done when

- [x] A repeatable comparison report exists.
- [x] Every returned chunk keeps its source metadata.
- [x] The chosen configuration has measured benefits and its limitations are documented.

## Run the experiments

```sh
# Retrieval comparison only; rewriting/reranking still make paid chat calls.
.venv/bin/python -m app.compare_retrieval

# Full comparison, including generated answers and the same answer rubric for all modes.
.venv/bin/python -m app.compare_retrieval --answers

# Recheck saved answers/sections against the current worksheet without API calls.
.venv/bin/python -m app.compare_retrieval --rescore
```

The detailed report, including all answers, usage, timings, source version, worksheet snapshot/hash, and configuration, is `.rag/retrieval-comparison.json`. It stays ignored because outputs can contain local knowledge. Each completed case is saved; failed cases stay in the denominator. [04-results.md](04-results.md) contains the shareable aggregate report.

The worksheet is `steps/04-retrieval-examples.json`: 22 questions, 19 with positive source labels and three with missing-policy expectations. It targets the local Jagel corpus; adapt it for another source. Initial 18-question vector-only measurements are superseded by the expanded comparison.

## Implementation

- **Keyword/BM25:** local, no new dependency or API. Unicode word tokens, small English/Indonesian stop-word list, k1=1.2, b=0.75. Repeated root titles are excluded. No stemming or synonym dictionary.
- **Vector:** existing Fireworks Qwen3 embedding, cosine similarity, minimum 0.30. That threshold applies only to vector candidates.
- **Hybrid:** each search contributes up to ten candidates; equal-weight reciprocal rank fusion sums `1 / (60 + rank)`, deterministic chunk-ID ties. The fused list is bounded to the candidate limit. Scores are not confidence values.
- **Rewriting:** optional Fireworks chat call, current question plus bounded earlier-user context. Instructions ask for a self-contained query without changing names, constraints, numbers, or negations. The original search query remains first and the expansion is capped at 800 characters, so the rewrite cannot remove original terms. It can still introduce a misleading expansion; disabled by default.
- **Reranking:** optional Fireworks chat call reorders bounded candidate passages. Only an exact permutation of the submitted IDs is accepted; unknown, missing, duplicate, or malformed IDs trigger the original ranking. Passage text is capped at 18,000 serialized characters; candidates beyond that budget retain their order at the tail. Text is labeled untrusted data. Rewriting/reranking each have a six-second limit and 700 output tokens, with no extra retries; malformed/incomplete/provider-error/timeout responses preserve the original query/ranking. The existing whole-chat 30-second deadline remains.
- **Final evidence:** inheritance expansion, deduplication, original chunk identity/metadata, source freshness checks, and citation validation remain intact. Limits can be reduced but cannot exceed six passages/8,500 context characters.

## Selected configuration

**Keyword-only is the default for this small knowledge file.** In this run it matched the other improved variants' source recall and answer-rubric score while using fewer calls and lower latency/cost. Hybrid remains available for semantic questions; these measurements do not establish keyword-only as best for other corpora or unseen questions. Re-evaluate after knowledge or workload changes.

```dotenv
RAG_SEARCH_MODE=keyword
RAG_CANDIDATES=10
RAG_TOP_K=3
RAG_MAX_PASSAGES=6
RAG_CONTEXT_CHARACTERS=8500
RAG_REWRITE=false
RAG_RERANK=false
```

For a hybrid/reranking experiment, set `RAG_SEARCH_MODE=hybrid` and `RAG_RERANK=true`. Use `RAG_REWRITE=true` to experiment with rewriting. Both flags can be enabled, although that combination was not evaluated. Restart after configuration edits; no re-ingestion is needed. Optional model assistance always uses the Fireworks chat model even when the reply provider is OpenAI.

## Evaluation boundaries and known issue

Section Recall@3 measures expected section labels among the first three ranked candidates; evidence recall separately checks the actual bounded, inheritance-expanded context. Unanswerable cases are excluded from recall and tested for abstention instead. Section labels are not exhaustive chunk-level relevance/precision labels.

Answer screening checks required fact/term groups, validated source citations, and `unknown` plus human escalation for missing policies. It is not a semantic correctness judge. Manual review corrected one rubric false negative: “compile ulang” was accepted alongside “APK” for the logo rebuild question. All saved answers were rescored consistently, and broad Firebase/remote/transfer labels were narrowed to the relevant leaf sections without additional generation calls.

Manual review of the chosen keyword-mode answers and all failed/abstention cases found a remaining failure: the driver-menu question is interpreted as creating a courier menu instead of locating the Driver menu in the generated app. Every variant failed the corresponding check despite having the Bronze source. This is an answer interpretation/knowledge-disambiguation issue; do not claim the chatbot is fully accurate. Some Firebase replies also add UI navigation detail beyond the exact source wording, which the term rubric does not penalize. Owner review remains necessary.

Single run, small non-held-out worksheet, stochastic answers, and no confidence intervals: the results support a provisional choice, not broad superiority. No model training or LangChain was added.

## Verification

Backend tests cover keyword ranking, fusion, configuration bounds, no-embedding keyword mode, rewrite constraint retention and fallback, invalid reranking IDs, bounded context/metadata, metrics, and usage cost calculations. Existing chat/history/citation checks remain required. The local server is restarted after completion so the selected configuration can be tested.

References: [SQLite BM25 explanation](https://www.sqlite.org/fts5.html#the_bm25_function), [Elastic reciprocal rank fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion), [Fireworks pricing](https://fireworks.ai/pricing).
