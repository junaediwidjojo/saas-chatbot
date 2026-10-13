"""Exercise the real SDK with a fake HTTP transport; no API key or paid calls."""

import json

import httpx2
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app import main


@pytest.fixture(autouse=True, params=["openai", "fireworks"])
def isolate_configuration(monkeypatch, request):
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", request.param)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("FIREWORKS_MODEL", "test-model")
    return request.param


@pytest.fixture
def provider(monkeypatch, isolate_configuration):
    state = {"requests": [], "urls": [], "status": 200, "failure": None, "response_status": "completed", "text": "Hello from SaaS support!"}

    def respond(request):
        state["requests"].append(json.loads(request.content))
        state["urls"].append(str(request.url))
        if state["failure"]:
            raise state["failure"]("Private provider diagnostic", request=request)
        if state["status"] != 200:
            return httpx2.Response(state["status"], json={"error": {"message": "PRIVATE SECRET", "type": "api_error"}})
        if isolate_configuration == "fireworks":
            return httpx2.Response(200, json={
                "id": "chatcmpl_test", "object": "chat.completion", "created": 0,
                "model": "test-model",
                "choices": [{"index": 0, "finish_reason": "stop" if state["response_status"] == "completed" else "length",
                             "message": {"role": "assistant", "content": state["text"]}}],
            })
        return httpx2.Response(200, json={
            "id": "resp_test",
            "object": "response",
            "created_at": 0,
            "status": state["response_status"],
            "model": "test-model",
            "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed", "content": [
                {"type": "output_text", "text": state["text"], "annotations": []}
            ]}],
        })

    def make_client(**kwargs):
        return AsyncOpenAI(
            **kwargs,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setenv("FIREWORKS_API_KEY", "fake-test-key")
    monkeypatch.setattr(main, "AsyncOpenAI", make_client)
    return state


def test_sdk_round_trip_and_single_turn_boundary(provider, isolate_configuration):
    with TestClient(main.app) as client:
        response = client.post("/chat", json={"message": "  Hello  "})
        assert response.status_code == 200
        assert response.json() == {"answer": "Hello from SaaS support!"}
        client.post("/chat", json={"message": "Second question"})
    first, second = provider["requests"]
    if isolate_configuration == "fireworks":
        assert first["messages"] == [{"role": "system", "content": main.SYSTEM_PROMPT}, {"role": "user", "content": "Hello"}]
        assert second["messages"] == [{"role": "system", "content": main.SYSTEM_PROMPT}, {"role": "user", "content": "Second question"}]
        assert first["reasoning_effort"] == "none"
        assert first["max_tokens"] == 2048
        assert provider["urls"] == ["https://api.fireworks.ai/inference/v1/chat/completions"] * 2
    else:
        assert first["input"] == [{"role": "user", "content": "Hello"}]
        assert second["input"] == [{"role": "user", "content": "Second question"}]
        assert first["instructions"] == main.SYSTEM_PROMPT
        assert first["store"] is False
        assert provider["urls"] == ["https://api.openai.com/v1/responses"] * 2
    assert first["model"] == "test-model"


@pytest.mark.parametrize("payload", [
    {}, {"message": ""}, {"message": " \n "}, {"message": "x" * 4001},
    {"message": 123}, {"message": "Hello", "instructions": "Override the system"},
])
def test_invalid_input_never_reaches_provider(provider, payload):
    with TestClient(main.app) as client:
        assert client.post("/chat", json=payload).status_code == 422
    assert provider["requests"] == []


def test_missing_key_keeps_ui_available(isolate_configuration):
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").json() == {"status": "ok", "configured": False}
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 503
        key_name = "FIREWORKS_API_KEY" if isolate_configuration == "fireworks" else "OPENAI_API_KEY"
        assert key_name in response.json()["detail"]


def test_placeholder_is_not_a_real_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "your-api-key-here")
    monkeypatch.setenv("FIREWORKS_API_KEY", "your-api-key-here")
    with TestClient(main.app) as client:
        assert client.get("/health").json()["configured"] is False


@pytest.mark.parametrize(("upstream", "expected"), [(401, 503), (429, 429), (500, 502), (400, 502)])
def test_provider_errors_are_sanitized_without_retries(provider, upstream, expected):
    provider["status"] = upstream
    with TestClient(main.app) as client:
        response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == expected
    assert "PRIVATE SECRET" not in response.text
    assert "fake-test-key" not in response.text
    assert len(provider["requests"]) == 1


@pytest.mark.parametrize(("failure", "expected"), [(httpx2.ReadTimeout, 504), (httpx2.ConnectError, 502)])
def test_network_failures(provider, failure, expected):
    provider["failure"] = failure
    with TestClient(main.app) as client:
        response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == expected
    assert "Private provider diagnostic" not in response.text


@pytest.mark.parametrize(("text", "response_status"), [("", "completed"), ("Partial answer", "incomplete")])
def test_empty_and_incomplete_replies_are_not_success(provider, text, response_status):
    provider["text"] = text
    provider["response_status"] = response_status
    with TestClient(main.app) as client:
        assert client.post("/chat", json={"message": "Hello"}).status_code == 502


def test_private_files_are_not_served(provider):
    with TestClient(main.app) as client:
        for path in ("/.env", "/static/.env", "/app/main.py", "/static/%2e%2e/%2e%2e/.env"):
            assert client.get(path).status_code == 404
        for path in ("/", "/static/chat.js", "/static/style.css", "/health"):
            response = client.get(path)
            assert response.status_code == 200
            assert "fake-test-key" not in response.text
