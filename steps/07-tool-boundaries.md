# Step 07 — Controlled tools and authorization

Status: Not started

## Goal

Expand tool access through deterministic application boundaries.

## Prerequisite

Complete step 06 first.

## What you will learn

Services, repositories, authentication, authorization, least privilege, tool contracts.

## Build checklist

- [ ] Separate tool dispatch, business services, and repositories; expose no arbitrary SQL execution tool.
- [ ] Add get_order, get_shipping_status, get_customer_orders, get_product, search_products, and check_return_eligibility as needed.
- [ ] Derive customer identity from the trusted backend session. Scope every customer-data query to that identity.
- [ ] Implement return eligibility in deterministic code using versioned policy rules consistent with the knowledge documents and an explicit clock.
- [ ] Validate identifiers and constrain search results and tool payload sizes.
- [ ] Add meaningful tests for cross-customer access, malformed arguments, injection attempts, and return-window boundaries.
- [ ] Document the development identity limitation; implement real authentication before exposing private customer data beyond local fixtures.

## Done when

- [ ] Customer-data tools enforce ownership independently of model instructions.
- [ ] The model cannot submit raw SQL or choose another authenticated identity.
- [ ] Eligibility boundaries are covered by deterministic checks.

## Scope

Keep write actions out of the tool registry until step 09.

## Build request

> Build step 07 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Record implementation decisions, run commands, verification results, and remaining limitations here after building.
