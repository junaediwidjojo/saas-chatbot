# Step 01 — Ordinary chatbot

Status: Implemented; live API smoke check pending

## Goal

Connect a minimal chat interface to an LLM through a backend.

## Prerequisite

Start from this documentation-only folder.

## What you will learn

System and user messages, API integration, tokens, context windows, prompt basics.

## Build checklist

- [x] Choose and document the backend, frontend, LLM provider, and package manager when this step begins. Python with FastAPI is a reasonable starting point; keep the UI minimal.
- [x] Create the smallest runnable app with a POST /chat endpoint and a text input plus message display.
- [x] Call the provider SDK directly. Keep credentials on the backend and provide an .env.example with placeholders.
- [x] Use a fictional SaaS company as the scenario. Send a short system prompt and the current user message.
- [x] Handle empty input, missing configuration, provider timeouts, and provider errors with useful messages.
- [x] Record a few baseline questions and observations, including a policy question the model cannot reliably answer.

## Done when

- [ ] A message travels from the UI through the backend to the live LLM and the response appears in the UI. Simulated-provider browser round trip passed; live verification requires an API key.
- [x] No API key appears in browser code, logs, or committed files.
- [x] README includes exact local setup and run commands.

## Scope

No retrieval, database, agent framework, persistent memory, or company-policy claims yet.

## Build request

> Build step 01 using this document. Explain the core concepts, implement only this step, verify the completion criteria, and update the progress tracker.

## Completion notes

Implemented on 2026-09-25.

- Stack: Python 3.14.6, FastAPI, Uvicorn, plain browser JavaScript, Fireworks Chat Completions or OpenAI Responses API, and pip with pinned dependencies. The model is configurable through `.env`.
- Run: follow the exact setup commands in [README](../README.md), then run `.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
- Verification: 36 backend tests pass across OpenAI and Fireworks; dependency consistency and JavaScript syntax checks pass. Tests use the actual SDK with a simulated HTTP transport and make no paid calls.
- Browser: verified missing-key feedback, restored draft after failure, and a successful simulated-provider round trip. Model output containing HTML markup remains plain text.
- Baselines: [questions, observed checks, and live-run worksheet](01-baseline.md).
- Limitation: no API key was configured during implementation. No real model output or factual accuracy is claimed. The remaining completion checkbox intentionally stays open.
- Scope: only the current message is sent; no retrieval, database, tools, durable memory, or structured model output is implemented.
