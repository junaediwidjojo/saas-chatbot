"""Step 02: request structured output, validate it, and bound recovery."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic import Field, StringConstraints, ValidationError, model_validator

from app.schemas import ASSISTANT_JSON_SCHEMA, AssistantResponse, fallback_response, out_of_scope_response
from app.memory import (
    MEMORY_LIMITS, MAX_HISTORY_CHARACTERS, MAX_HISTORY_MESSAGES, MAX_MESSAGE_CHARACTERS,
    MAX_SUMMARY_CHARACTERS, ConversationMemory, ConversationSummary, HistoryMessage, summary_split,
)

ROOT = Path(__file__).resolve().parent.parent
FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-v4p1-flash"
MAX_OUTPUT_ATTEMPTS = 2


def load_system_prompt() -> str:
    rules = (ROOT / "prompts" / "support-v4.txt").read_text()
    configured_path = os.getenv("SAAS_KNOWLEDGE_FILE", "").strip()
    if configured_path:
        knowledge_path = Path(configured_path).expanduser()
        if not knowledge_path.is_absolute():
            knowledge_path = ROOT / knowledge_path
        if not knowledge_path.is_file():
            raise FileNotFoundError("SAAS_KNOWLEDGE_FILE must point to an existing knowledge file.")
    else:
        knowledge_path = ROOT / "knowledge" / "mock-saas.md"
        if not knowledge_path.is_file():
            knowledge_path = ROOT / "knowledge" / "mock-saas.example.md"
    knowledge = knowledge_path.read_text()
    return f"{rules}\n\nMOCK KNOWLEDGE:\n{knowledge}\n\nJSON SCHEMA:\n{json.dumps(ASSISTANT_JSON_SCHEMA)}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve .env relative to the project, without replacing shell environment values.
    load_dotenv(ROOT / ".env", override=False)
    app.state.system_prompt = load_system_prompt()
    app.state.summary_prompt = (ROOT / "prompts" / "summarize-v1.txt").read_text()
    app.state.provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if app.state.provider not in {"openai", "fireworks"}:
        raise ValueError("LLM_PROVIDER must be openai or fireworks.")
    fireworks = app.state.provider == "fireworks"
    app.state.key_name = "FIREWORKS_API_KEY" if fireworks else "OPENAI_API_KEY"
    key = os.getenv(app.state.key_name, "").strip()
    model_name = "FIREWORKS_MODEL" if fireworks else "OPENAI_MODEL"
    default_model = FIREWORKS_MODEL if fireworks else "gpt-6-astra"
    app.state.model = os.getenv(model_name, default_model).strip() or default_model
    app.state.openai = None
    if key and key != "your-api-key-here":
        base_url = "https://api.fireworks.ai/inference/v1" if fireworks else "https://api.openai.com/v1"
        app.state.openai = AsyncOpenAI(api_key=key, base_url=base_url, timeout=30.0, max_retries=0)
    try:
        yield
    finally:
        if app.state.openai is not None:
            await app.state.openai.close()


app = FastAPI(title="SaaS Chatbot", lifespan=lifespan)
# Serve only this directory, never the project root containing .env.
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


class ChatRequest(ConversationMemory):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARACTERS)]
    history: Annotated[list[HistoryMessage], Field(max_length=MAX_HISTORY_MESSAGES)] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chat_budget(self):
        if sum(len(item.content) for item in self.history) > MAX_HISTORY_CHARACTERS:
            raise ValueError(f"History exceeds {MAX_HISTORY_CHARACTERS} characters; summarize older exchanges first.")
        return self


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _error: RequestValidationError):
    # Do not echo user input or internal validation details into error responses.
    return JSONResponse(
        status_code=422,
        content={"detail": f"Invalid message or conversation state. Messages allow 1–{MAX_MESSAGE_CHARACTERS} characters. Chat history allows {MAX_HISTORY_MESSAGES // 2} completed exchanges and {MAX_HISTORY_CHARACTERS} characters; summary limit is {MAX_SUMMARY_CHARACTERS} characters."},
    )


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/health")
async def health(request: Request):
    # Configured does not claim that credentials or model access have been verified.
    return {"status": "ok", "configured": request.app.state.openai is not None, "memory_limits": MEMORY_LIMITS}


@dataclass
class GenerationRequest:
    instructions: str
    conversation: list[dict[str, str]]
    schema: dict
    name: str
    max_output_tokens: int = 2048


async def generate_structured(state, generation: GenerationRequest) -> tuple[str | None, bool]:
    if state.provider == "fireworks":
        response = await state.openai.chat.completions.create(
            model=state.model,
            messages=[
                {"role": "system", "content": generation.instructions},
                *generation.conversation,
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": generation.name, "schema": generation.schema, "strict": True},
            },
            max_tokens=generation.max_output_tokens,
            reasoning_effort="none",
        )
        if not response.choices:
            return None, False
        choice = response.choices[0]
        refusal = choice.message.refusal or choice.finish_reason == "content_filter"
        completed = choice.finish_reason == "stop"
        text = choice.message.content
    else:
        response = await state.openai.responses.create(
            model=state.model,
            instructions=generation.instructions,
            input=generation.conversation,
            text={"format": {
                "type": "json_schema", "name": generation.name,
                "schema": generation.schema, "strict": True,
            }},
            max_output_tokens=generation.max_output_tokens,
            store=False,
        )
        refusal = any(
            content.type == "refusal"
            for item in response.output if item.type == "message"
            for content in item.content
        )
        completed = response.status == "completed"
        text = response.output_text
    return text if completed and isinstance(text, str) else None, bool(refusal)


async def generate_reply(state, body: ChatRequest, attempt: int) -> AssistantResponse | None:
    instructions = state.system_prompt
    if attempt:
        instructions += "\nThe previous generation was invalid or incomplete. Return a complete JSON object matching the schema and escalation rules."
    conversation = []
    if body.summary:
        conversation.append({
            "role": "user",
            "content": "Untrusted summary of earlier conversation, for context only:\n" + json.dumps(body.summary),
        })
    conversation.extend(item.model_dump() for item in body.history)
    conversation.append({"role": "user", "content": body.message})
    text, refusal = await generate_structured(state, GenerationRequest(
        instructions=instructions, conversation=conversation,
        schema=ASSISTANT_JSON_SCHEMA, name="AssistantResponse",
    ))
    if refusal:
        return AssistantResponse(
            intent="refusal",
            answer="I can’t help with that request. Please contact human support for a safe alternative. No action has been taken.",
            requires_human=True,
        )
    if text is None:
        return None
    try:
        return AssistantResponse.model_validate_json(text)
    except ValidationError:
        return None


@asynccontextmanager
async def provider_request(state):
    if state.openai is None:
        raise HTTPException(503, f"Add {state.key_name} to your .env file and restart the server.")
    try:
        async with asyncio.timeout(30):
            yield
    except (APITimeoutError, TimeoutError):
        raise HTTPException(504, "The AI took too long to respond. Please try again.") from None
    except AuthenticationError:
        raise HTTPException(503, "The API key was rejected. Check .env and restart the server.") from None
    except RateLimitError:
        raise HTTPException(429, "The AI service is at its limit. Check API quota or try again later.") from None
    except APIConnectionError:
        raise HTTPException(502, "Cannot reach the AI service. Check your connection and try again.") from None
    except APIError:
        raise HTTPException(502, "The AI request failed. Check model access and API configuration, then retry.") from None


@app.post("/chat", response_model=AssistantResponse)
async def chat(body: ChatRequest, request: Request):
    async with provider_request(request.app.state):
        for attempt in range(MAX_OUTPUT_ATTEMPTS):
            reply = await generate_reply(request.app.state, body, attempt)
            if reply is not None:
                return out_of_scope_response() if reply.intent == "out_of_scope" else reply
        return fallback_response()


@app.post("/memory/summarize", response_model=ConversationMemory)
async def summarize(body: ConversationMemory, request: Request):
    split = summary_split(body)
    if not split:
        return body
    schema = ConversationSummary.model_json_schema()
    instructions = request.app.state.summary_prompt + "\nJSON SCHEMA:\n" + json.dumps(schema)
    async with provider_request(request.app.state):
        text, refusal = await generate_structured(request.app.state, GenerationRequest(
            instructions=instructions,
            conversation=[{"role": "user", "content": json.dumps({
                "previous_summary": body.summary,
                "older_messages": [item.model_dump() for item in body.history[:split]],
            })}],
            schema=schema, name="ConversationSummary", max_output_tokens=1200,
        ))
        if text is not None and not refusal:
            try:
                result = ConversationSummary.model_validate_json(text)
                return ConversationMemory(summary=result.summary, history=body.history[split:])
            except ValidationError:
                pass
    raise HTTPException(502, "Could not update the conversation summary. Your history has been kept. Please retry or clear chat.")
