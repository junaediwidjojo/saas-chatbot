# Step 08 — Combine RAG and tools

Status: Not started

## Goal

Answer questions that need both company policy and customer facts.

## Prerequisite

Complete step 07 first.

## What you will learn

Routing, bounded orchestration, evidence combination, error handling.

## Build checklist

- [ ] Expose knowledge retrieval alongside the controlled read-only tools.
- [ ] Support “Can I return the headphones from my last order?” by locating the order item, retrieving policy, and checking deterministic eligibility.
- [ ] Ask for clarification when multiple items match instead of guessing.
- [ ] Include policy citations and clearly distinguish retrieved policy from live order facts.
- [ ] Handle stale or conflicting policy versions, missing purchase details, and unavailable tools without declaring unsupported eligibility.
- [ ] Limit tool calls and add basic traces for retrieval, tool selection, and response generation.

## Done when

- [ ] A seeded return scenario uses both policy retrieval and authenticated order tools.
- [ ] The final decision matches the deterministic eligibility result.
- [ ] Ambiguous items and partial failures produce a useful next step.

## Scope

The LLM explains the result; application code determines authorization and eligibility.

## Build request

> Build step 08 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
