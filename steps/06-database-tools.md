# Step 06 — Read-only database tools

Status: Not started

## Goal

Answer order questions using application data instead of document retrieval.

## Prerequisite

Complete step 05 first.

## What you will learn

PostgreSQL, schema design, tool schemas, tool execution, trusted customer identity.

## Build checklist

- [ ] Add PostgreSQL, migrations, and fictional seed customers, orders, order items, products, shipments, and returns.
- [ ] Establish a server-controlled development identity for seeded customers; never trust a customer ID supplied by the model as authentication.
- [ ] Implement get_order_status(order_id) with validated arguments, parameterized database access, and an ownership check.
- [ ] Expose its schema to the LLM, execute allowed calls in the backend, and pass sanitized results back for the final answer.
- [ ] Bound tool iterations and handle invalid arguments, unknown tools, unavailable databases, and missing orders.
- [ ] Keep customer records out of the public knowledge index and redact sensitive tool data from logs.

## Done when

- [ ] A customer receives the seeded status of their own order.
- [ ] Another customer cannot access that order by guessing its ID.
- [ ] Missing orders and database failures never produce invented statuses.

## Scope

Read-only tools only. Authorization applies from the first database integration, even though the next step expands it.

## Build request

> Build step 06 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
