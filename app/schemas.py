"""Step 02 response contract, shared by provider requests and HTTP responses."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_CITATIONS = 6


class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal[
        "general", "product", "pricing", "policy", "account",
        "action_request", "unknown", "refusal", "fallback", "out_of_scope",
    ]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    requires_human: bool
    confidence: Annotated[float | None, Field(ge=0, le=1)] = None
    citation_ids: Annotated[list[str], Field(max_length=MAX_CITATIONS)] = Field(default_factory=list)

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


class SourceCitation(BaseModel):
    id: str
    title: str
    section: str
    version: str


class ChatResponse(AssistantResponse):
    citations: list[SourceCitation] = Field(default_factory=list)


def cited_response(reply: AssistantResponse, chunks) -> ChatResponse | None:
    by_id = {chunk.id: chunk for chunk in chunks}
    if any(cid not in by_id for cid in reply.citation_ids) or len(set(reply.citation_ids)) != len(reply.citation_ids):
        return None
    if reply.intent in {"product", "pricing", "policy"} and not reply.citation_ids:
        return None
    citations = [SourceCitation(id=cid, title=by_id[cid].title, section=by_id[cid].section, version=by_id[cid].version)
                 for cid in reply.citation_ids]
    return ChatResponse(**reply.model_dump(), citations=citations)


def fallback_response() -> AssistantResponse:
    return AssistantResponse(
        intent="fallback",
        answer="I couldn’t produce a reliable reply. Please rephrase your question or contact human support. No action has been taken.",
        requires_human=True,
    )


def out_of_scope_response() -> AssistantResponse:
    return AssistantResponse(
        intent="out_of_scope",
        answer="Saya khusus membantu pertanyaan tentang produk dan layanan kami. Silakan tanyakan fitur, paket, atau cara penggunaannya.",
        requires_human=False,
    )
