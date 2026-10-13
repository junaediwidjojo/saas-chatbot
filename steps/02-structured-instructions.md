# Step 02 — Structured instructions and outputs

Status: Not started

## Goal

Give the application a validated response contract and clearer behavior rules.

## Prerequisite

Complete step 01 first.

## What you will learn

Prompt design, structured outputs, schema validation, uncertainty, refusal and escalation.

## Build checklist

- [ ] Create a versioned system prompt: never invent policies or order facts, acknowledge missing information, keep answers concise, and report actions only after confirmed tool success.
- [ ] Define an AssistantResponse schema with intent, answer, requires_human, and optional confidence. Treat model confidence as an uncalibrated signal, never an authorization rule.
- [ ] Use provider-supported structured output where available and validate every response on the backend.
- [ ] Display answer in the chat UI while retaining structured fields for application logic.
- [ ] Bound retries for invalid output and return a clear fallback on persistent failure.
- [ ] Keep a small set of examples for unknown policies, missing orders, ordinary questions, and invalid responses.

## Done when

- [ ] The API returns a validated response shape.
- [ ] Unknown policy and order questions acknowledge missing information.
- [ ] Malformed provider output cannot crash the request or bypass validation.

## Scope

Do not add invented policy text to make the chatbot appear knowledgeable.

## Build request

> Build step 02 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
