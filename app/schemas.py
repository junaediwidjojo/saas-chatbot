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
    page: int | None = None  # 1-based manual page; None for Markdown knowledge.


class ChatResponse(AssistantResponse):
    citations: list[SourceCitation] = Field(default_factory=list)


class ProductIdentification(BaseModel):
    """Validated photo identification. Still a model proposal, never proof of the customer's device."""
    status: Literal["identified", "ambiguous", "not_supported", "unclear_image"]
    product_id: str | None = None
    product_name: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    candidate_names: list[str] = Field(default_factory=list)
    manual_available: bool = False


class PhotoChatResponse(ChatResponse):
    identification: ProductIdentification | None  # None when identification failed or was refused.


def cited_response(reply: AssistantResponse, chunks) -> ChatResponse | None:
    by_id = {chunk.id: chunk for chunk in chunks}
    if any(cid not in by_id for cid in reply.citation_ids) or len(set(reply.citation_ids)) != len(reply.citation_ids):
        return None
    if reply.intent in {"product", "pricing", "policy"} and not reply.citation_ids:
        return None
    citations = [SourceCitation(id=cid, title=by_id[cid].title, section=by_id[cid].section,
                                version=by_id[cid].version, page=by_id[cid].page)
                 for cid in reply.citation_ids]
    return ChatResponse(**reply.model_dump(), citations=citations)


def fallback_response() -> AssistantResponse:
    return AssistantResponse(
        intent="fallback",
        answer="I couldn’t produce a reliable reply. Please rephrase your question or contact human support. No action has been taken.",
        requires_human=True,
    )


def refusal_response() -> ChatResponse:
    return ChatResponse(
        intent="refusal",
        answer="I can’t help with that request. Please contact human support for a safe alternative. No action has been taken.",
        requires_human=True,
    )


def out_of_scope_response() -> AssistantResponse:
    return AssistantResponse(
        intent="out_of_scope",
        answer="Saya khusus membantu pertanyaan tentang produk dan layanan kami. Silakan tanyakan fitur, paket, atau cara penggunaannya.",
        requires_human=False,
    )
