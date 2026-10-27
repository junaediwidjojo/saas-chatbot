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


### Topic boundaries — 2026-10-20

- Active instructions are now `prompts/support-v2.txt`; v1 remains for comparison.
- Added `out_of_scope` for unrelated coding, math, poems, and trivia in any language, with Indonesian and English examples. Greetings and product support remain allowed. Mixed requests should answer only the product portion; unknown product facts still need human support.
- On `out_of_scope`, the backend replaces model answer, escalation, and confidence with a fixed Indonesian reminder, false, and null. No separate classification request is added.
- Regression checks verify replacement even when the model includes code and recommends escalation, plus preservation of a valid product-only answer to a mixed request. Simulations verify backend behavior, not the model's classification accuracy.
- Limit: a model that misclassifies an unrelated question can still produce an unrelated answer. Mixed-request filtering also depends on prompt compliance.
- Verification: 82 tests pass across both providers; dependency consistency, JavaScript syntax, and whitespace checks pass.
- Live Fireworks spot checks with committed example knowledge: Indonesian Fibonacci and English poem requests returned the fixed `out_of_scope` response without escalation; an Indonesian Team pricing question returned the documented price; a mixed pricing/Fibonacci request answered pricing and declined code generation. All returned HTTP 200. These four observations do not guarantee classification accuracy on every input.


### Bounded conversation history — 2026-10-20

- Added at the user's request before the planned durable-memory step. `support-v3` is active; earlier prompt versions remain historical.
- Browser sends up to five completed user/assistant exchanges, at most 16,000 characters total, before the current question. Per-message history limit: 4,000 characters. Older pairs are trimmed; no automatic summary is generated.
- Only successful displayed answers enter history, including safe fallback/scope reminders. Failed HTTP requests do not enter history. Clear chat and refresh reset it; no database, browser storage, provider conversation ID, or server-side history is used.
- Backend validates roles, alternating pairs, message count, and size; it supplies system rules itself. Historical text is untrusted context, never evidence of company facts, identity, permission, or completed actions.
- Verification: 114 backend tests pass across both providers, covering history forwarding/order, retry preservation, no server-side carryover, invalid roles, extra fields, malformed pairs, and boundary sizes.
- Browser checks with simulated replies verified follow-up payloads, failed-request exclusion, retry without duplicates, five-exchange and character-limit trimming (including emoji), metadata exclusion, Clear chat, and refresh reset.
- Live Fireworks browser spot check using the committed example: after asking the price of Team, “Berapa batas anggotanya?” correctly answered the Team member limit of 20. This verifies one follow-up, not general model accuracy.


### Rolling conversation summaries — 2026-10-27

- Added at the user's request using the existing SDK, without LangChain or new runtime dependencies. Active chat instructions: `support-v4`; summary instructions: `summarize-v1`.
- Browser keeps an existing summary plus recent completed exchanges. Before the next chat, `/memory/summarize` compacts older messages when history exceeds five exchanges/16,000 characters or an estimated 3,000 tokens. The estimate is ceil(UTF-8 bytes / 3) over summary and recent messages only, not a model tokenizer or hard full-context token budget.
- Shared backend constants in `app/memory.py` are supplied to the browser through `/health`. Summary limit: 2,000 characters. Compaction input limit: 12 messages/24,000 characters; chat limit remains 10 messages/16,000 characters. Each message is limited to 4,000 characters.
- Compaction usually preserves the newest two exchanges verbatim, retaining at least one pair. Its separate generation combines previous summary and older messages, excludes SaaS knowledge, and preserves user goals, named plans, preferences, unresolved issues, and corrections as conversation claims. Summary generation makes one call, capped at 1,200 output tokens within 30 seconds.
- Backend validates summary JSON before returning the new memory. The browser validates it and the unchanged history suffix before removing old pairs. On failure, it preserves history, summary, and draft. If compaction succeeds but chat fails, retry uses the successfully compacted state without duplicates.
- Summary is added as labeled untrusted user-level context, never inserted into system instructions. It cannot establish policy, identity, approval, or completed actions. Loss or distortion of details is still possible.
- Clear chat or refresh resets summary, recent history, and transcript. No server-side conversation state, persistence, conversation IDs, ownership/authentication, tools, or durable memory were added.
- Verification: 152 backend checks and four frontend-script tests pass. Frontend tests use a simulated DOM; they are not full browser end-to-end tests.
- Live Fireworks check with fictional data: summarized six exchanges to a summary plus the latest two exchanges. An early statement about 18 team members and monthly billing remained in the summary. A follow-up correctly recalled both as user-stated requirements (`product`, human support false), rather than claiming account verification. This is a spot check; summary fidelity is not guaranteed.
