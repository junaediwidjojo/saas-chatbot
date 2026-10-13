"""Step 02 response contract, shared by provider requests and HTTP responses."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal[
        "general", "product", "pricing", "policy", "account",
        "action_request", "unknown", "refusal", "fallback",
    ]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    requires_human: bool
    confidence: Annotated[float | None, Field(ge=0, le=1)] = None

    @model_validator(mode="after")
    def require_escalation(self):
        if self.intent in {"account", "action_request", "unknown", "refusal", "fallback"} and not self.requires_human:
            raise ValueError("This intent requires human support.")
        return self


# OpenAI strict output requires every property, including nullable optional ones.
# The backend also accepts omitted confidence and fills it with None.
ASSISTANT_JSON_SCHEMA = AssistantResponse.model_json_schema()
ASSISTANT_JSON_SCHEMA["required"] = list(ASSISTANT_JSON_SCHEMA["properties"])
ASSISTANT_JSON_SCHEMA["properties"]["confidence"].pop("default", None)


def fallback_response() -> AssistantResponse:
    return AssistantResponse(
        intent="fallback",
        answer="I couldn’t produce a reliable reply. Please rephrase your question or contact human support. No action has been taken.",
        requires_human=True,
    )
