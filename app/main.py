"""Step 02: request structured output, validate it, and bound recovery."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
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
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from app.schemas import ASSISTANT_JSON_SCHEMA, AssistantResponse, fallback_response, out_of_scope_response

ROOT = Path(__file__).resolve().parent.parent
FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-v4p1-flash"
MAX_OUTPUT_ATTEMPTS = 2


def load_system_prompt() -> str:
    rules = (ROOT / "prompts" / "support-v2.txt").read_text()
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


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _error: RequestValidationError):
    # Do not echo user input or internal validation details into error responses.
    return JSONResponse(
        status_code=422,
        content={"detail": "Send a message containing 1–4,000 characters."},
    )


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/health")
async def health(request: Request):
    # Configured does not claim that credentials or model access have been verified.
    return {"status": "ok", "configured": request.app.state.openai is not None}


async def generate_reply(state, message: str, attempt: int) -> AssistantResponse | None:
    instructions = state.system_prompt
    if attempt:
        # Do not echo malformed model output or private validation diagnostics.
        instructions += "\nThe previous generation was invalid or incomplete. Return a complete JSON object matching the schema and escalation rules."
    if state.provider == "fireworks":
        response = await state.openai.chat.completions.create(
            model=state.model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "AssistantResponse", "schema": ASSISTANT_JSON_SCHEMA, "strict": True},
            },
            max_tokens=2048,
            reasoning_effort="none",
        )
        if not response.choices:
            return None
        choice = response.choices[0]
        refusal = choice.message.refusal or choice.finish_reason == "content_filter"
        completed = choice.finish_reason == "stop"
        text = choice.message.content
    else:
        response = await state.openai.responses.create(
            model=state.model,
            instructions=instructions,
            input=[{"role": "user", "content": message}],
            text={"format": {
                "type": "json_schema", "name": "AssistantResponse",
                "schema": ASSISTANT_JSON_SCHEMA, "strict": True,
            }},
            max_output_tokens=2048,
            store=False,
        )
        refusal = any(
            content.type == "refusal"
            for item in response.output if item.type == "message"
            for content in item.content
        )
        completed = response.status == "completed"
        text = response.output_text
    if refusal:
        return AssistantResponse(
            intent="refusal",
            answer="I can’t help with that request. Please contact human support for a safe alternative. No action has been taken.",
            requires_human=True,
        )
    if not completed or not isinstance(text, str):
        return None
    try:
        return AssistantResponse.model_validate_json(text)
    except ValidationError:
        return None


@app.post("/chat", response_model=AssistantResponse)
async def chat(body: ChatRequest, request: Request):
    client = request.app.state.openai
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=f"Add {request.app.state.key_name} to your .env file and restart the server.",
        )

    try:
        # The original 30-second budget covers both attempts, not 30s per attempt.
        async with asyncio.timeout(30):
            for attempt in range(MAX_OUTPUT_ATTEMPTS):
                reply = await generate_reply(request.app.state, body.message, attempt)
                if reply is not None:
                    if reply.intent == "out_of_scope":
                        return out_of_scope_response()
                    return reply
        return fallback_response()
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
