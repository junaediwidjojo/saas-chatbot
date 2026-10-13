# Step 09 — Confirmed write actions

Status: Not started

## Goal

Let the chatbot cancel eligible orders through an explicit confirmation workflow.

## Prerequisite

Complete step 08 first.

## What you will learn

State machines, transactions, idempotency, confirmations, audit trails.

## Build checklist

- [ ] Start with cancellation only; keep other writes for later extensions.
- [ ] Check ownership and cancellation eligibility before presenting a concrete action summary.
- [ ] Store a pending action on the backend bound to the customer, conversation, order, action parameters, and an expiry time.
- [ ] Require explicit confirmation for that pending action before invoking cancel_order.
- [ ] Recheck authorization and eligibility inside the write transaction; handle an order shipping between proposal and confirmation.
- [ ] Use idempotency to prevent duplicate execution on repeated confirmation or retried requests.
- [ ] Record an audit event and report success only from a confirmed tool result.
- [ ] Cover rejection, expiry, changed state, repeated confirmation, and database failure.

## Done when

- [ ] An unconfirmed request never mutates an order.
- [ ] A confirmed eligible cancellation commits once and reports the actual result.
- [ ] Expired, mismatched, or newly ineligible actions are rejected.

## Scope

Use fictional data. Refunds, address changes, and external fulfillment integrations are out of scope.

## Build request

> Build step 09 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
