# Step 04 comparison results

Recorded: 2026-11-03. Five variants × 22 questions = 110 generated answers. Source SHA-256: `745c890a09b4f45d8b6a0c52be3c583ebee9d643cbc159009e4584142fa0c087`.

Worksheet SHA-256: `de2c69da079390450846f555844aaae114cf3b939c12ebfd864b6a49969defcf`. All variants use the same 22-question worksheet; 19 have expected source sections, three require acknowledging missing policies.

| Variant | Section Recall@3 | Evidence recall | Answer rubric | Median retrieval | Median total | Estimated USD / 22 questions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| vector | 89.5% | 94.7% | 86.4% | 309.75 ms | 2.46 s | $0.025466 |
| keyword | 100.0% | 100.0% | 95.5% | 0.23 ms | 2.05 s | $0.025271 |
| hybrid | 100.0% | 100.0% | 95.5% | 311.00 ms | 2.36 s | $0.027509 |
| hybrid_rerank | 100.0% | 100.0% | 95.5% | 1969.78 ms | 4.13 s | $0.051899 |
| hybrid_rewrite | 100.0% | 100.0% | 95.5% | 1311.36 ms | 3.28 s | $0.028065 |

**Decision:** use keyword-only for this corpus; leave rewriting/reranking off. It tied the improved variants on both recall and the screening rubric, with the lowest observed total latency and estimated cost. Hybrid remains configurable, but this run did not demonstrate enough benefit to choose its extra query embedding call. No variant made all answers correct.

All 110 requests completed. The optional reranker fell back to the original ranking in five of its 22 cases. Those cases remain included in the results; a valid permutation is required to replace the ranking.

Cost estimates use API-reported token usage and standard uncached rates: DeepSeek-V4.1-Flash input $0.30/M, output $1.20/M, Qwen3 8B embeddings $0.10/M. [Fireworks pricing](https://fireworks.ai/pricing), checked 2026-11-03. Estimates ignore cache discounts, special service tiers, taxes and costs outside this run; they are not billed totals. Full comparison estimate: $0.158210.

Unlike the preliminary comparison, each variant makes its own network requests; query vectors are not reused between variants. Two questions run concurrently; variant order rotates across questions. Timings cover retrieval and, for total time, validated answer generation and any generation retry. They exclude index/client startup. Single-run network and output-length variation prevent treating small latency differences as definitive.

Answer rubric = required fact/term groups plus validated citations for factual answers; missing-policy cases require unknown intent and human escalation. This is not full factual accuracy. Manual review accepted equivalent “compile ulang” wording and rescored all saved outputs consistently. Source labels were narrowed to leaf sections. The report stores the final worksheet and hash; no answers were regenerated during rescoring.

Manual review covered all chosen keyword-mode answers and every failed/abstention case across variants. All variants misinterpreted the driver-menu question as courier-menu setup despite retrieving Bronze. Vector-only additionally missed the logo rebuild evidence and produced an incomplete tariff explanation. Some otherwise passing Firebase answers add UI-navigation detail beyond the exact source text. These limitations remain visible, rather than being filtered from the denominator.

Small, non-held-out set; no repeated trials or confidence intervals. Recall uses section-name labels rather than exhaustive chunk relevance, and unknown-policy questions are excluded from recall. Do not generalize 100% worksheet recall to production accuracy.

Reproduce with `.venv/bin/python -m app.compare_retrieval --answers`. Detailed answers, per-request token usage, source metadata, fallback flags, timings, and options are in the ignored `.rag/retrieval-comparison.json`. The same command can yield different answers on a later run. Use `--rescore` to apply the current worksheet to saved results without API calls.
