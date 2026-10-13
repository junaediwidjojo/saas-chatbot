# Step 11 — Evaluation and observability

Status: Not started

## Goal

Make quality, safety, latency, and cost changes measurable.

## Prerequisite

Complete step 10 first.

## What you will learn

Evaluation datasets, regression checks, tracing, scoring, operational tradeoffs.

## Build checklist

- [ ] Consolidate examples collected in earlier steps into a versioned JSONL dataset; start small and grow toward roughly 200 meaningful cases.
- [ ] Include expected tools and arguments, relevant sources, answer criteria, permitted actions, and authorization outcomes.
- [ ] Cover policy questions, multimodal examples, follow-ups, confirmation flows, tool failures, prompt injection, and cross-customer access.
- [ ] Build an evaluation command with fixed seed data, an explicit clock, and recorded model, prompt, and retrieval versions.
- [ ] Measure retrieval Recall@K, tool and argument accuracy, groundedness, factual correctness, authorization violations, and task completion.
- [ ] Record latency, token usage, and cost estimates with the pricing assumptions and date. Redact sensitive content in traces.
- [ ] Use deterministic scoring where possible; document uncertainty and human review for model-judged metrics.
- [ ] Define regression thresholds and produce a readable comparison report. Consider routing or optimization only after a measured baseline.

## Done when

- [ ] The evaluation suite can be run with a documented command and produces a reproducible report.
- [ ] Critical authorization and unconfirmed-write cases have zero violations.
- [ ] The report separates retrieval failures, tool failures, and answer failures.

## Scope

Evaluation examples begin in step 01; this step consolidates them into a full harness. Deployment is a separate future decision.

## Build request

> Build step 11 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
