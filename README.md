# SaaS Chatbot

A staged AI engineering learning project: build a customer-support chatbot for a fictional **SaaS company**, one concept at a time.

Step 01 is implemented with Python, FastAPI, a plain HTML/CSS/JavaScript frontend, and the official OpenAI SDK. Local checks pass; the live model smoke check awaits an API key. No database has been initialized. The Git repository is hosted at [junaediwidjojo/saas-chatbot](https://github.com/junaediwidjojo/saas-chatbot).

## How we will build it

1. Ask to build a step, for example: **“Build step 01 for saas-chatbot.”**
2. Read that step's document and complete only its scope.
3. Explain the concepts and implementation choices as we build.
4. Verify its completion criteria, record commands and decisions, and update the table below.
5. Wait for your request before starting the next step.

The backend uses Python with FastAPI and pip. The frontend is served by the same backend, so no Node build or separate frontend server is required. LLM requests use the OpenAI SDK: Fireworks Chat Completions for DeepSeek, or the OpenAI Responses API when OpenAI is selected. Use fictional customer data throughout the learning project.

## Run locally

Python 3.11+ is required; this build was verified with Python 3.14.6. On this Mac, use Homebrew's Python explicitly: Xcode's Python is 3.9 and cannot install the pinned dependencies.

```sh
cd /Users/junaediwidjojo/HobbyProjects/saas-chatbot
/opt/homebrew/bin/python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-lock.txt
cp -n .env.example .env
```

Edit `.env` locally and configure Fireworks with DeepSeek-V4.1-Flash:

```dotenv
LLM_PROVIDER=fireworks
FIREWORKS_API_KEY=your-api-key-here
FIREWORKS_MODEL=accounts/fireworks/models/deepseek-v4p1-flash
```

Replace `your-api-key-here` with a key from [Fireworks API Keys](https://app.fireworks.ai/settings/users/api-keys). Keep the key in `.env`, which Git ignores. The backend sends requests to `https://api.fireworks.ai/inference/v1/chat/completions`; no additional SDK is required. Thinking is disabled (`reasoning_effort="none"`) so the 2,048-token budget is used for the final answer.

`cp -n` preserves an existing `.env`, so update its values manually if needed. To use OpenAI instead, set `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL` to a Responses API model you can access. A Codex or ChatGPT sign-in does not configure this application's API key.

```sh
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [the chatbot](http://127.0.0.1:8000). API documentation is at [localhost:8000/docs](http://127.0.0.1:8000/docs). Restart the server after changing `.env`; a shell environment variable takes precedence over the file. Stop the server with Ctrl+C.

These commands do not require activation. Using `.venv/bin/python` directly avoids a shell alias or function sending `python` to Xcode's interpreter even when the prompt shows `(.venv)`. For another machine, replace `/opt/homebrew/bin/python3.14` with the path to an installed Python 3.11+ interpreter. Check the environment with `.venv/bin/python --version` and `.venv/bin/python -m pip --version`; pip's path should be inside `.venv`.

Without a key, the interface still loads and shows a setup message. Once configured, each Send calls your selected provider and may incur API usage charges. This is a local learning app, with no authentication or deployment setup.

`requirements.txt` pins direct runtime dependencies, `requirements-dev.txt` adds test dependencies, and `requirements-lock.txt` records the full tested environment. The setup above installs the full lock, including tests.

## Try it

Ask “What can you help me with?” and then “What is your return policy?” The second question demonstrates the missing-knowledge problem: no company policies have been supplied to the model. The prompt asks it to acknowledge that, but prompt instructions alone are not a correctness guarantee.

The UI offers sample questions, Enter to send, Shift+Enter for new lines, and Clear chat. A failed request restores your question so you can retry. The visible transcript is only in the current browser page; each model request receives **only the latest question**.

A direct API check:

```sh
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What can you help me with?"}'
```

A successful response is JSON with an `answer` string. Errors return a readable `detail` string. Input is limited to 4,000 characters, provider requests time out after 30 seconds, and automatic SDK retries are disabled. Output is capped at 2,048 tokens; incomplete replies are reported as errors.

## How step 01 works

```text
Browser (chat.js)
  → POST /chat with {"message": "..."}
  → FastAPI validates the message
  → OpenAI SDK sends instructions + a user message
  → Backend reads the final answer text
  → Browser displays {"answer": "..."} as plain text
```

- **Instructions:** the backend's short system prompt defines the assistant's role and acknowledges missing store data.
- **User message:** the customer's question is separate from those instructions.
- **Tokens:** models process chunks of text, not a fixed number of words. Input characters and output tokens have separate limits here.
- **Context window:** the maximum input/output context a model can handle. In this stage, context consists of instructions plus one question; the screen's transcript is not sent.
- **Prompt design:** changing the instructions changes behavior, but cannot supply facts the application does not have.
- **Conversation history:** follow-up references such as “it” may fail because prior messages are absent. We add durable memory in step 10.

The endpoint's `ChatResponse` is just an HTTP response shape. It does not request structured model output; that remains step 02. No temperature setting, retrieval, tools, or agent framework is added in this step. Fireworks requests disable reasoning for this simple baseline.

## Verify

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

The 36 backend cases exercise the real OpenAI SDK with simulated HTTP responses. They cover both provider paths, make no paid calls and ignore your `.env` and API key. Coverage includes single-turn payloads, blank/oversized input, missing keys, provider errors, timeouts, empty/incomplete replies, and private-file access.

Browser verification covered the missing-key message and retry behavior, and a full send/receive round trip against a temporary simulated provider. This verifies plumbing, not model quality. Record real model observations using [the baseline checklist](steps/01-baseline.md) after configuring your key.

## Files to read first

- `app/main.py` — prompt, provider lifecycle, input validation, and chat endpoint.
- `app/static/index.html` — chat page structure.
- `app/static/chat.js` — send, render, clear, and retry behavior.
- `app/static/style.css` — responsive layout and visual styling.
- `tests/test_chat.py` — isolated SDK and API checks.

Official references: [Fireworks OpenAI compatibility](https://docs.fireworks.ai/tools-sdks/openai-compatibility), [DeepSeek V4.1 Flash on Fireworks](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash), [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart) and [text generation](https://developers.openai.com/api/docs/guides/text).

## Progress

| Step | Build guide | Status |
| --- | --- | --- |
| 01 | [Ordinary chatbot](steps/01-ordinary-chatbot.md) | Implemented; live API check pending |
| 02 | [Structured instructions and outputs](steps/02-structured-instructions.md) | Not started |
| 03 | [First text RAG](steps/03-first-rag.md) | Not started |
| 04 | [Improve retrieval](steps/04-better-retrieval.md) | Not started |
| 05 | [Multimodal RAG](steps/05-multimodal-rag.md) | Not started |
| 06 | [Read-only database tools](steps/06-database-tools.md) | Not started |
| 07 | [Controlled tools and authorization](steps/07-tool-boundaries.md) | Not started |
| 08 | [Combine RAG and tools](steps/08-rag-and-tools.md) | Not started |
| 09 | [Confirmed write actions](steps/09-confirmed-actions.md) | Not started |
| 10 | [Conversation memory](steps/10-conversation-memory.md) | Not started |
| 11 | [Evaluation and observability](steps/11-evaluation-and-observability.md) | Not started |

## Target capabilities

- Answer company-policy and product questions with citations.
- Read manuals and identify supported products from images.
- Retrieve a customer's own orders using controlled tools.
- Combine policy evidence with live data for return questions.
- Cancel eligible orders after explicit confirmation.
- Understand conversation follow-ups without mixing customer data.
- Measure retrieval quality, tool correctness, task completion, latency, and cost.

## Architecture we will grow toward

```text
Chat UI → Chat API → Orchestrator → LLM
                         ├── Retrieval → Knowledge and manuals
                         ├── Tools → Services → PostgreSQL
                         └── Memory → Conversation state

Across the system: validation, authorization, traces, and evaluation.
```

The step order follows the supplied learning plan. Authorization starts with the first database tool, and small verification examples accumulate from the first stage. Step 07 expands tool boundaries; step 11 turns those examples into a comprehensive evaluation system.
