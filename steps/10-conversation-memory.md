# Step 10 — Conversation memory

Status: Durable memory not started; browser history and rolling summaries available

## Goal

Resolve follow-up questions with bounded, isolated conversation state.

## Prerequisite

Complete step 09 first.

## What you will learn

Context budgets, summaries, structured state, persistence, freshness.

## Build checklist

- [ ] Add conversation IDs and persist recent messages with customer ownership.
- [ ] Track relevant order and product references in structured state.
- [x] Use a bounded recent-message window plus summaries for longer conversations. Implemented early on 2026-10-27 as browser-owned state; durable ownership and persistence remain pending.
- [ ] Resolve “Can I cancel it?” from prior context and ask for clarification when references are ambiguous.
- [ ] Re-fetch live order facts before answering time-sensitive questions or taking actions.
- [ ] Keep pending confirmations in authoritative backend state; summaries cannot create approval or override authorization.
- [ ] Provide a conversation reset and document retention behavior for local data.

## Done when

- [ ] Follow-up pronouns resolve correctly in a representative conversation.
- [ ] Long conversations stay within the configured context budget.
- [ ] State cannot leak between customers or conversations, and resetting clears conversational references.

## Scope

Basic message history may exist earlier; this step introduces durable, bounded memory.

## Build request

> Build step 10 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Rolling summaries and bounded recent history were added early at the user’s request. See the 2026-10-27 notes in [Step 02](02-structured-instructions.md). This does not complete the durable-memory step: conversation IDs, customer ownership, persisted state, structured references, freshness checks, and authoritative confirmations remain unimplemented.
