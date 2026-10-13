# Step 02 — Structured instructions and outputs

Status: Implemented; live behavior verification recorded below

## Goal

Give the application a validated response contract and clearer behavior rules.

## Prerequisite

Complete step 01 first.

## What you will learn

Prompt design, structured outputs, schema validation, uncertainty, refusal and escalation.

## Build checklist

- [x] Create a versioned system prompt: never invent policies or order facts, acknowledge missing information, keep answers concise, and report actions only after confirmed tool success.
- [x] Define an AssistantResponse schema with intent, answer, requires_human, and optional confidence. Treat model confidence as an uncalibrated signal, never an authorization rule.
- [x] Use provider-supported structured output where available and validate every response on the backend.
- [x] Display answer in the chat UI while retaining structured fields for application logic.
- [x] Bound retries for invalid output and return a clear fallback on persistent failure.
- [x] Keep a small set of examples for unknown policies, missing orders, ordinary questions, and invalid responses.

## Done when

- [x] The API returns a validated response shape.
- [x] Unknown policy and order questions acknowledge missing information.
- [x] Malformed provider output cannot crash the request or bypass validation.

## Scope

The user explicitly requested mock SaaS knowledge for this build. A clearly labeled fictional CloudDesk dataset is committed in `knowledge/mock-saas.example.md`; the customizable `knowledge/mock-saas.md` and `knowledge/local/` directory are ignored by Git. Unsupported policies and private records remain unknown. The full selected file is sent as context, without retrieval, a database, tools, or persistent memory.

## Build request

> Build step 02 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Implemented on 2026-10-13 on `feat/step-02-structured-responses`.

- Versioned behavior: `prompts/support-v1.txt`; local editable facts: ignored `knowledge/mock-saas.md`, with fallback to committed `knowledge/mock-saas.example.md`. Optional `SAAS_KNOWLEDGE_FILE` selects another file (relative to the project root or absolute); an explicitly configured missing file fails startup. Restart the server after changes. Tests use only the committed example.
- Contract: `app/schemas.py` defines strict intent, nonblank answer, boolean requires_human, and optional nullable confidence in [0, 1]. Extra fields and incorrect types are rejected. Selected intents require human support, regardless of confidence.
- Provider generation: Fireworks uses Chat Completions `response_format`; OpenAI uses Responses `text.format`. Both request JSON schema output. Confidence is required but nullable in the provider schema for OpenAI strict compatibility; the backend also accepts omission and supplies null.
- Recovery: at most two generations inside one 30-second budget. Invalid/incomplete JSON is retried once without echoing provider output. Persistent failure returns a validated fallback. Explicit provider refusals are normalized without retry. Network/provider errors retain sanitized HTTP errors.
- UI: displays answer as plain text, retains structured fields in page memory, and adds a support recommendation. No ticket, message, lookup, or action is performed. Confidence is not shown as a reliability score.
- Examples: `02-examples.json` covers ordinary help, documented pricing, unknown refunds, missing orders, unavailable actions, and refusal. These are illustrative targets, not automatically graded live model results.
- Validation: 74 simulated SDK/backend checks pass, including schema rejection, retry bounds/recovery, incomplete replies, provider refusals, timeouts, input validation, and private-file access. JavaScript syntax and Git whitespace checks pass. These checks make no provider calls.
- Run: `.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
- Verify: `.venv/bin/python -m pytest -q`; `node --check app/static/chat.js`.
- Browser: verified a live refund question through UI → backend → Fireworks → UI. The answer appeared as text, the response metadata was retained, and the support recommendation stated that no ticket was created. A simulated HTML-containing answer remained literal text; Clear chat removed the transcript and metadata.
- Limits: shape validation cannot prove factual correctness or prevent all prompt injection. There are no real account records or tools. Human escalation is a recommendation only. The original Step 01 baseline observations remain historical; the live connection was verified using the current Step 02 prompt.

### Live model observations

Verified on 2026-10-13 using Fireworks `accounts/fireworks/models/deepseek-v4p1-flash` through the real backend. All four API requests returned HTTP 200 with validated fields; these are spot checks, not a general model-quality guarantee.

| Question | Observed result |
| --- | --- |
| How much does the Team plan cost? | `pricing`, human support false; answered USD 29 per workspace/month, 20 members, unlimited boards, labeled as demo information. |
| What is your refund policy? | `unknown`, human support true; acknowledged absent refund information and pointed to Help → Contact support. |
| Where is order 12345? | `account`, human support true; acknowledged no order/customer-record access. |
| Cancel my subscription now. | `action_request`, human support true; said it could not cancel or confirm escalation, and gave the demo settings path. |

The refund question was also sent from the actual browser, where the answer and human-support note appeared successfully. No real customer facts or credentials were submitted in these checks.
