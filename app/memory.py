"""Bounded, browser-owned conversation state and summary selection."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_MESSAGE_CHARACTERS = 4000
MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_CHARACTERS = 16000
MAX_SUMMARY_CHARACTERS = 2000
MAX_PENDING_MESSAGES = MAX_HISTORY_MESSAGES + 2
MAX_PENDING_CHARACTERS = MAX_HISTORY_CHARACTERS + 2 * MAX_MESSAGE_CHARACTERS
SUMMARY_TRIGGER_TOKENS = 3000
RECENT_MESSAGES_TO_KEEP = 4
TOKEN_ESTIMATE_BYTES = 3

MEMORY_LIMITS = {
    "message_characters": MAX_MESSAGE_CHARACTERS,
    "history_messages": MAX_HISTORY_MESSAGES,
    "history_characters": MAX_HISTORY_CHARACTERS,
    "summary_characters": MAX_SUMMARY_CHARACTERS,
    "summary_trigger_tokens": SUMMARY_TRIGGER_TOKENS,
    "token_estimate_bytes": TOKEN_ESTIMATE_BYTES,
}


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARACTERS,
    )]


class ConversationMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_SUMMARY_CHARACTERS)] = ""
    history: Annotated[list[HistoryMessage], Field(max_length=MAX_PENDING_MESSAGES)] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_history(self):
        if len(self.history) % 2:
            raise ValueError("History must contain completed exchanges.")
        if any(item.role != ("user" if index % 2 == 0 else "assistant") for index, item in enumerate(self.history)):
            raise ValueError("History must alternate user and assistant messages.")
        if sum(len(item.content) for item in self.history) > MAX_PENDING_CHARACTERS:
            raise ValueError(f"Pending history exceeds {MAX_PENDING_CHARACTERS} characters.")
        return self


class ConversationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_SUMMARY_CHARACTERS,
    )]


def estimated_tokens(memory: ConversationMemory) -> int:
    # This is a size heuristic, not the provider's tokenizer or billing count.
    byte_count = len(memory.summary.encode("utf-8")) + sum(
        len(item.content.encode("utf-8")) for item in memory.history
    )
    return (byte_count + TOKEN_ESTIMATE_BYTES - 1) // TOKEN_ESTIMATE_BYTES


def needs_summary(memory: ConversationMemory) -> bool:
    return len(memory.history) > MAX_HISTORY_MESSAGES or sum(
        len(item.content) for item in memory.history
    ) > MAX_HISTORY_CHARACTERS or estimated_tokens(memory) > SUMMARY_TRIGGER_TOKENS


def summary_split(memory: ConversationMemory) -> int:
    if not needs_summary(memory) or len(memory.history) < 4:
        return 0
    split = max(2, len(memory.history) - RECENT_MESSAGES_TO_KEEP)
    # Preserve at least the latest completed exchange; only remove whole pairs.
    while split < len(memory.history) - 2:
        recent = ConversationMemory(summary=memory.summary, history=memory.history[split:])
        if not needs_summary(recent):
            break
        split += 2
    return split
