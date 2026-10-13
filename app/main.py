"""Step 01: browser → FastAPI → configured model provider → browser."""

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
from pydantic import BaseModel, ConfigDict, StringConstraints

ROOT = Path(__file__).resolve().parent.parent
FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-v4p1-flash"
SYSTEM_PROMPT = (
    "You are the customer support assistant for a fictional SaaS company. "
    "Be friendly and concise. You do not have store policies or order data yet; "
    "say when you cannot answer rather than inventing those details."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve .env relative to the project, without replacing shell environment values.
    load_dotenv(ROOT / ".env", override=False)
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


class ChatResponse(BaseModel):
    answer: str


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


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    client = request.app.state.openai
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=f"Add {request.app.state.key_name} to your .env file and restart the server.",
        )

    try:
        if request.app.state.provider == "fireworks":
            response = await client.chat.completions.create(
                model=request.app.state.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": body.message},
                ],
                max_tokens=2048,
                # Keep the output budget for the final answer in this baseline app.
                reasoning_effort="none",
            )
            completed = bool(response.choices) and response.choices[0].finish_reason == "stop"
            answer = (response.choices[0].message.content or "").strip() if response.choices else ""
        else:
            response = await client.responses.create(
                model=request.app.state.model,
                instructions=SYSTEM_PROMPT,
                input=[{"role": "user", "content": body.message}],
                max_output_tokens=2048,
                store=False,
            )
            completed = response.status == "completed"
            answer = response.output_text.strip()
    except APITimeoutError:
        raise HTTPException(504, "The AI took too long to respond. Please try again.") from None
    except AuthenticationError:
        raise HTTPException(503, "The API key was rejected. Check .env and restart the server.") from None
    except RateLimitError:
        raise HTTPException(429, "The AI service is at its limit. Check API quota or try again later.") from None
    except APIConnectionError:
        raise HTTPException(502, "Cannot reach the AI service. Check your connection and try again.") from None
    except APIError:
        raise HTTPException(502, "The AI request failed. Check model access and API configuration, then retry.") from None

    if not completed:
        raise HTTPException(502, "The AI could not finish its reply. Please try a shorter question.")
    if not answer:
        raise HTTPException(502, "The AI returned no text. Please rephrase your question.")
    return ChatResponse(answer=answer)
