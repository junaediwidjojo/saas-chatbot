# SaaS Chatbot

A staged AI engineering learning project: build a customer-support chatbot for a fictional **SaaS company**, one concept at a time.

Steps 01 and 02 are implemented with Python, FastAPI, a plain HTML/CSS/JavaScript frontend, and the official OpenAI SDK. Replies now follow a validated contract and use clearly fictional CloudDesk knowledge. No database has been initialized. The Git repository is hosted at [junaediwidjojo/saas-chatbot](https://github.com/junaediwidjojo/saas-chatbot).

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

Open [the chatbot](http://127.0.0.1:8000). API documentation is at [localhost:8000/docs](http://127.0.0.1:8000/docs). Restart the server after changing `.env`, prompt files, or mock knowledge; a shell environment variable takes precedence over the file. Stop the server with Ctrl+C.

These commands do not require activation. Using `.venv/bin/python` directly avoids a shell alias or function sending `python` to Xcode's interpreter even when the prompt shows `(.venv)`. For another machine, replace `/opt/homebrew/bin/python3.14` with the path to an installed Python 3.11+ interpreter. Check the environment with `.venv/bin/python --version` and `.venv/bin/python -m pip --version`; pip's path should be inside `.venv`.

Without a key, the interface still loads and shows a setup message. Once configured, each Send calls your selected provider and may incur API usage charges. This is a local learning app, with no authentication or deployment setup.

`requirements.txt` pins direct runtime dependencies, `requirements-dev.txt` adds test dependencies, and `requirements-lock.txt` records the full tested environment. The setup above installs the full lock, including tests.

## Try it

Ask “How much does the Team plan cost?” and then “What is your refund policy?” The first question uses the supplied fictional plans; the second should acknowledge that refund information is missing. Also try “Where is order 12345?” and “Cancel my subscription now.” The assistant has no private records or tools. Prompt instructions and a valid schema do not guarantee factual correctness.

The UI offers sample questions, Enter to send, Shift+Enter for new lines, and Clear chat. A failed request restores your question so you can retry. The visible transcript, recent history, and rolling summary stay in page memory. Each chat request sends the latest question, a summary of older discussion when available, and recent completed exchanges. Clear chat or refresh resets all three. Failed HTTP requests do not enter history; successful fallback and scope reminders do, exactly as displayed.

Before the next chat, the browser requests a summary update when history exceeds five completed exchanges, 16,000 characters, or an estimated 3,000 history tokens. The estimate is UTF-8 bytes divided by three, rounded up; it is a trigger heuristic, not the provider tokenizer, exact usage, or a hard total-context token limit. System instructions, SaaS knowledge, and the latest question are outside that estimate. Hard character/count limits still bound every request.

The backend summarizes the existing summary plus older exchanges, usually preserving the latest two exchanges verbatim (at least one). It returns the new summary, limited to 2,000 characters, and the unchanged recent messages. Only after this response is validated does the browser replace its summary and remove older pairs. The visible transcript remains intact. Recent chat history is capped at ten messages/16,000 characters, each message at 4,000 characters. The summary endpoint allows one extra completed exchange in transit (12 messages/24,000 characters) so nothing must be dropped before compaction.

A summary update makes one extra provider call, capped at 1,200 output tokens and 30 seconds. It runs only when needed. Invalid, refused, incomplete, or failed summary generation leaves local context and the draft intact; retry or Clear chat to continue. A successful compaction remains valid even if the subsequent chat fails, so retry uses that summary without duplicating messages. Summaries are lossy: important omissions or mistakes are possible, and ambiguous references should be clarified.

A direct API check:

```sh
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What can you help me with?"}'
```

Successful replies follow this contract:

```json
{
  "intent": "unknown",
  "answer": "The demo knowledge does not include a refund policy. Please contact human support.",
  "requires_human": true,
  "confidence": null
}
```

The UI displays `answer`, keeps the structured fields in page memory, and shows a human-support recommendation when `requires_human` is true. It does not contact anyone or perform account actions. Confidence is an optional, uncalibrated model estimate, never an authorization rule.

Input is limited to 4,000 characters. Each generation is capped at 2,048 tokens. Malformed, incomplete, or schema-invalid output gets one fresh retry, within a total 30-second budget. Persistent invalid output returns a validated `fallback` response with `requires_human=true`. Provider/network failures return readable HTTP errors with a `detail` string; automatic SDK retries remain disabled.

## How the current app works

```text
Browser (chat.js)
  → POST /chat with {"message": "..."}
  → FastAPI validates the message
  → OpenAI SDK sends versioned instructions + mock knowledge + untrusted summary + recent exchanges + the current question
  → Provider generates JSON using a supplied schema
  → Backend validates types, fields, and escalation rules (one retry if invalid)
  → Browser displays answer as plain text and retains response metadata
```

- **Instructions:** the versioned prompt defines the assistant’s role, uncertainty, refusal, and action boundaries.
- **User message:** the customer's question is separate from those instructions.
- **Tokens:** models process chunks of text, not a fixed number of words. Input characters and output tokens have separate limits here.
- **Context window:** the maximum input/output context a model can handle. In this stage, context consists of instructions, the full mock knowledge file, the schema, a bounded summary, recent history, and the latest question; only the bounded recent history is sent, not necessarily the entire visible transcript.
- **Prompt design:** changing the instructions changes behavior, but cannot supply facts the application does not have.
- **Conversation history:** recent exchanges retain exact wording; a rolling summary carries older goals, preferences, references, unresolved questions, and corrections. The backend accepts only user/assistant pairs; system instructions always come from the server. Browser history and summaries are untrusted context, not proof of facts, identity, or completed actions. Durable storage remains Step 10.

Step 02 adds provider-enforced JSON schema output and strict Pydantic backend validation using `AssistantResponse`. Extra fields, incorrect types, empty answers, invalid intents, and out-of-range confidence are rejected. Account, action, unknown, refusal, and fallback intents must recommend human support. The validator checks structure and these rules; it cannot prove that model text is truthful or that the chosen intent is correct.

## Topic boundaries

The active prompt is `support-v4`; earlier prompt versions are preserved for comparison. Greetings and SaaS support questions are allowed. Unrelated code, mathematics, poems, and trivia use `out_of_scope`. The backend discards the model's answer and returns a fixed Indonesian scope reminder with `requires_human=false` and `confidence=null`. This uses the existing single generation on the normal path; no separate classifier call is added.

Mixed requests should answer only the product-related portion and decline the rest. Missing product facts still use `unknown` and recommend human support. Classification and mixed-answer compliance depend on the model; the fixed reply applies only when it selects `out_of_scope`. Restart the server to load the new prompt.

## Adjust the mock knowledge

The committed [knowledge/mock-saas.example.md](knowledge/mock-saas.example.md) supplies fictional features, prices, trial terms, cancellation instructions, and support hours. It intentionally omits refund terms, an SLA, and private customer records. Create your local copy without overwriting an existing file:

```sh
cp -n knowledge/mock-saas.example.md knowledge/mock-saas.md
```

Edit `knowledge/mock-saas.md` freely; Git ignores it. Your existing local file is preserved. Without a custom path setting, the app uses this local file if present and otherwise uses the committed example, so fresh checkouts work immediately.

For a different dataset, put it in the ignored `knowledge/local/` directory and set its path in your ignored `.env`:

```dotenv
SAAS_KNOWLEDGE_FILE=knowledge/local/my-saas.md
```

Relative paths resolve from the project root; absolute paths are also supported. An explicitly configured file must exist; a typo stops startup rather than silently loading the demo. Files elsewhere in the repository need their own ignore rules. Restart the server after changing the file or setting. Knowledge is sent to your selected model provider, even though Git ignores the local file. The current prompt and UI still identify this stage as fictional demo data.

Edit [prompts/support-v4.txt](prompts/support-v4.txt) to experiment with behavior rules; create a new version and update the loader when changing the prompt version. [steps/02-examples.json](steps/02-examples.json) contains illustrative responses to compare with live replies, not claims about actual model answers.

The whole knowledge file is included in each request. This is direct context injection, with no search, embeddings, database, tools, or persistent memory. Retrieval begins in Step 03.

## Verify

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
node --test tests/history.test.cjs
```

The 152 backend cases exercise the real OpenAI SDK with simulated HTTP responses. They cover both provider paths, make no paid calls and ignore your `.env` and API key. Coverage includes requests with and without history, history roles/order/size limits, retry preservation, rolling summaries, failed/refused/invalid summary generation, summary input limits, blank/oversized input, missing keys, provider errors, timeouts, empty/incomplete replies, schema-invalid JSON, bounded recovery, refusals, and private-file access.

Browser verification covered the missing-key message and retry behavior, a simulated-provider round trip, and a live Fireworks refund question with a human-support recommendation. HTML-containing output stayed plain text, and Clear chat removed response metadata. Four live Step 02 API spot checks covered pricing, unknown refunds, missing orders, and unavailable cancellation. Use the [Step 02 examples and completion notes](steps/02-structured-instructions.md) to compare live model behavior with the contract; the [Step 01 baseline](steps/01-baseline.md) preserves the original stage’s observations.

The four frontend tests run the actual chat script with a simulated DOM and provider responses. They cover compaction before chat, rolling updates, preservation on summary failure, chat retry after compaction, UTF-8 size triggers, and reset behavior. They use Node’s built-in test runner; no frontend dependencies are installed.

## Files to read first

- `app/main.py` — prompt loading, provider lifecycle, structured generation, retries, and chat endpoint.
- `app/schemas.py` — response contract and validated fallback.
- `app/memory.py` — shared memory limits, validation, size heuristic, and selection of older exchanges.
- `prompts/summarize-v1.txt` — summary update instructions.
- `prompts/support-v4.txt` — versioned behavior rules.
- `knowledge/mock-saas.example.md` — committed fictional example; `knowledge/mock-saas.md` is your ignored local copy.
- `app/static/index.html` — chat page structure.
- `app/static/chat.js` — send, render, clear, and retry behavior.
- `app/static/style.css` — responsive layout and visual styling.
- `tests/test_chat.py` — isolated SDK and API checks.

Official references: [Fireworks OpenAI compatibility](https://docs.fireworks.ai/tools-sdks/openai-compatibility), [DeepSeek V4.1 Flash on Fireworks](https://fireworks.ai/models/deepseek-ai/deepseek-v4p1-flash), [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart) and [text generation](https://developers.openai.com/api/docs/guides/text).

## Progress

| Step | Build guide | Status |
| --- | --- | --- |
| 01 | [Ordinary chatbot](steps/01-ordinary-chatbot.md) | Implemented; live UI connection verified during Step 02 |
| 02 | [Structured instructions and outputs](steps/02-structured-instructions.md) | Implemented; mock knowledge and validated replies |
| 03 | [First text RAG](steps/03-first-rag.md) | Not started |
| 04 | [Improve retrieval](steps/04-better-retrieval.md) | Not started |
| 05 | [Multimodal RAG](steps/05-multimodal-rag.md) | Not started |
| 06 | [Read-only database tools](steps/06-database-tools.md) | Not started |
| 07 | [Controlled tools and authorization](steps/07-tool-boundaries.md) | Not started |
| 08 | [Combine RAG and tools](steps/08-rag-and-tools.md) | Not started |
| 09 | [Confirmed write actions](steps/09-confirmed-actions.md) | Not started |
| 10 | [Conversation memory](steps/10-conversation-memory.md) | Durable memory not started; rolling summaries + recent browser history available |
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
