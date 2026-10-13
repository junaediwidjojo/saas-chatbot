# Step 10 — Conversation memory

Status: Not started

## Goal

Resolve follow-up questions with bounded, isolated conversation state.

## Prerequisite

Complete step 09 first.

## What you will learn

Context budgets, summaries, structured state, persistence, freshness.

## Build checklist

- [ ] Add conversation IDs and persist recent messages with customer ownership.
- [ ] Track relevant order and product references in structured state.
- [ ] Use a bounded recent-message window plus summaries for longer conversations.
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

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
