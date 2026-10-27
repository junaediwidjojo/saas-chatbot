"""Small local vector index: Markdown sections, persisted vectors, exact cosine search."""

import hashlib
import json
import math
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from openai import AsyncOpenAI

from app.knowledge import knowledge_path, project_path
from app.schemas import MAX_CITATIONS

CHUNK_CHARACTERS = 1800
MAX_CONTEXT_CHARACTERS = 8500
MAX_PASSAGES = MAX_CITATIONS
TOP_K = 3
MIN_SIMILARITY = 0.30
EMBEDDING_BATCH_SIZE = 16
QUERY_CHARACTERS = 1600
CHUNKER_VERSION = "markdown-sections-v1"


class RagUnavailable(Exception):
    pass


@dataclass(frozen=True)
class RagConfig:
    source: Path
    index: Path
    model: str
    dimensions: int

    @classmethod
    def from_environment(cls):
        dimensions = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "512"))
        if not 32 <= dimensions <= 4096:
            raise ValueError("RAG_EMBEDDING_DIMENSIONS must be between 32 and 4096.")
        index = project_path(os.getenv("RAG_INDEX_FILE", ".rag/knowledge.sqlite3")).resolve()
        static = project_path("app/static").resolve()
        if index == static or static in index.parents:
            raise ValueError("RAG_INDEX_FILE must be outside app/static.")
        return cls(knowledge_path().resolve(), index, os.getenv("RAG_EMBEDDING_MODEL", "fireworks/qwen3-embedding-8b"), dimensions)


@dataclass
class Chunk:
    id: str
    title: str
    section: str
    text: str
    version: str
    related_ids: list[str]


@dataclass
class RetrievalResult:
    chunks: list[Chunk]

    def context(self) -> str:
        return json.dumps([asdict(chunk) for chunk in self.chunks], ensure_ascii=False)


def document_version(source: Path) -> str:
    return hashlib.sha256(source.read_bytes()).hexdigest()


def chunk_document(source: Path) -> list[Chunk]:
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    version = hashlib.sha256(raw).hexdigest()
    source_id = hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:10]
    sections = []
    headings = []
    lines = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            if lines and headings:
                sections.append((list(headings), "\n".join(lines).strip()))
            depth = len(match[1])
            headings = [item for item in headings if item[0] < depth] + [(depth, match[2])]
            lines = []
        else:
            lines.append(line)
    if lines and headings:
        sections.append((list(headings), "\n".join(lines).strip()))
    chunks = []
    ancestors = {}
    occurrences = {}
    for headings, body in sections:
        if not body.strip("- \n"):
            continue
        path = " > ".join(title for _, title in headings)
        ancestors[path] = body
        # Include direct parent introductions (e.g. a trial applying to every plan).
        parent = " > ".join(title for _, title in headings[:-1])
        intro = ancestors.get(parent, "") if len(headings) > 2 else ""
        content = (intro + "\n\n" + body).strip() if intro else body
        occurrence = occurrences.get(path, 0)
        occurrences[path] = occurrence + 1
        section_id = hashlib.sha256(f"{path}:{occurrence}".encode()).hexdigest()[:10]
        parts = []
        current = ""
        for paragraph in content.split("\n\n"):
            # Hard-split unusually long paragraphs; never omit a tail.
            for offset in range(0, len(paragraph), CHUNK_CHARACTERS):
                piece = paragraph[offset:offset + CHUNK_CHARACTERS]
                if current and len(current) + len(piece) + 2 > CHUNK_CHARACTERS:
                    parts.append(current)
                    current = ""
                current = (current + "\n\n" + piece).strip()
        if current:
            parts.append(current)
        for part, body_part in enumerate(parts):
            chunks.append(Chunk(f"{source_id}-{section_id}-{part}", headings[0][1], path, body_part, version, []))
    # Keep inheritance explicit, rather than assuming vector similarity follows it.
    plans = {}
    for chunk in chunks:
        match = re.search(r"Paket\s+(\w+)", chunk.section.split(" > ")[-1], re.I)
        if match:
            plans.setdefault(match[1].casefold(), []).append(chunk.id)
    for chunk in chunks:
        inheritance = " ".join(line for line in chunk.text.splitlines() if re.search(r"semua fitur", line, re.I))
        for plan, ids in plans.items():
            if re.search(rf"\b{re.escape(plan)}\b", inheritance, re.I):
                chunk.related_ids.extend(cid for cid in ids if cid != chunk.id)
    if not chunks:
        raise ValueError("Knowledge must contain non-empty Markdown sections with headings.")
    return chunks


def normalize(vector: list[float], dimensions: int) -> list[float]:
    if len(vector) != dimensions or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in vector):
        raise RagUnavailable("Embedding dimensions or values are invalid; check RAG configuration.")
    norm = math.sqrt(sum(x * x for x in vector))
    if not norm:
        raise RagUnavailable("The embedding provider returned a zero vector.")
    return [x / norm for x in vector]


class FireworksEmbedder:
    def __init__(self, config: RagConfig):
        self.config = config
        key = os.getenv("FIREWORKS_API_KEY", "").strip()
        if not key or key == "your-api-key-here":
            raise RagUnavailable("Add FIREWORKS_API_KEY to .env to enable retrieval embeddings.")
        self.client = AsyncOpenAI(api_key=key, base_url="https://api.fireworks.ai/inference/v1", timeout=30, max_retries=0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self.client.embeddings.create(model=self.config.model, input=texts, dimensions=self.config.dimensions)
        ordered = sorted(result.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(texts))):
            raise RagUnavailable("The embedding provider returned an incomplete batch.")
        return [normalize(item.embedding, self.config.dimensions) for item in ordered]

    async def close(self):
        await self.client.close()


async def ingest(config: RagConfig, embedder) -> dict:
    chunks = chunk_document(config.source)
    config.index.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.index) as db:
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, payload TEXT NOT NULL, vector TEXT NOT NULL)")
        old_meta = dict(db.execute("SELECT key,value FROM metadata"))
        cache = {}
        if old_meta.get("model") == config.model and old_meta.get("dimensions") == str(config.dimensions) and old_meta.get("chunker") == CHUNKER_VERSION:
            for cid, payload, vector in db.execute("SELECT id,payload,vector FROM chunks"):
                cached = json.loads(payload)
                cache[(cid, cached["section"], cached["text"])] = vector
        vectors = {}
        pending = []
        for chunk in chunks:
            cached = cache.get((chunk.id, chunk.section, chunk.text))
            if cached:
                vectors[chunk.id] = cached
            else:
                pending.append(chunk)
        for offset in range(0, len(pending), EMBEDDING_BATCH_SIZE):
            batch = pending[offset:offset + EMBEDDING_BATCH_SIZE]
            encoded = await embedder.embed([f"{chunk.section}\n{chunk.text}" for chunk in batch])
            if len(encoded) != len(batch):
                raise RagUnavailable("Embedding batch size mismatch.")
            for chunk, vector in zip(batch, encoded):
                vectors[chunk.id] = json.dumps(normalize(vector, config.dimensions))
        if document_version(config.source) != chunks[0].version:
            raise RagUnavailable("Knowledge changed during ingestion. Please run ingestion again.")
        # Publish the entire snapshot together; a failed embedding leaves the old rows intact.
        db.execute("DELETE FROM chunks")
        db.executemany("INSERT INTO chunks VALUES (?,?,?)", [(c.id, json.dumps(asdict(c)), vectors[c.id]) for c in chunks])
        db.execute("DELETE FROM metadata")
        metadata = {"model":config.model, "dimensions":str(config.dimensions), "chunker":CHUNKER_VERSION,
                    "source":str(config.source), "version":chunks[0].version}
        db.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
    return {"chunks":len(chunks), "embedded":len(pending), "reused":len(chunks) - len(pending), "version":chunks[0].version}


class Retriever:
    def __init__(self, config: RagConfig, embedder):
        self.config = config
        self.embedder = embedder
        self.chunks = {}
        self.vectors = {}
        if not config.index.is_file():
            raise RagUnavailable("Knowledge index is missing. Run .venv/bin/python -m app.ingest and restart the server.")
        try:
            with sqlite3.connect(f"{config.index.as_uri()}?mode=ro", uri=True) as db:
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
                expected = {"source":str(config.source), "model":config.model, "dimensions":str(config.dimensions), "chunker":CHUNKER_VERSION}
                if any(metadata.get(key) != value for key, value in expected.items()):
                    raise RagUnavailable("RAG configuration changed. Re-ingest knowledge and restart the server.")
                self.version = metadata["version"]
                for cid, payload, vector in db.execute("SELECT id,payload,vector FROM chunks"):
                    self.chunks[cid] = Chunk(**json.loads(payload))
                    self.vectors[cid] = normalize(json.loads(vector), config.dimensions)
        except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
            raise RagUnavailable("Knowledge index is invalid. Re-ingest knowledge and restart the server.") from exc
        self.check_freshness()

    def check_freshness(self):
        if not self.chunks or not self.config.source.is_file() or document_version(self.config.source) != self.version:
            raise RagUnavailable("Knowledge changed or is empty. Re-ingest knowledge and restart the server.")

    async def retrieve(self, query: str) -> RetrievalResult:
        self.check_freshness()
        text = "Instruct: Given a SaaS support question, retrieve passages that answer it.\nQuery:" + query[:QUERY_CHARACTERS]
        vector = (await self.embedder.embed([text]))[0]
        ranked = sorted(self.chunks, key=lambda cid: sum(a * b for a, b in zip(vector, self.vectors[cid])), reverse=True)
        selected = []
        used_characters = 0

        def include(cid):
            nonlocal used_characters
            if cid in {chunk.id for chunk in selected} or cid not in self.chunks:
                return
            chunk = self.chunks[cid]
            size = len(json.dumps(asdict(chunk), ensure_ascii=False))
            if len(selected) >= MAX_PASSAGES or used_characters + size > MAX_CONTEXT_CHARACTERS - 100:
                return
            selected.append(chunk)
            used_characters += size + 2
            for related in chunk.related_ids:
                include(related)

        for cid in ranked[:TOP_K]:
            score = sum(a * b for a, b in zip(vector, self.vectors[cid]))
            if score >= MIN_SIMILARITY:
                include(cid)
        return RetrievalResult(selected)


def retrieval_query(body) -> str:
    # Current question first; only user context resolves references. Old assistant claims
    # must not steer retrieval toward invented facts.
    pieces = [body.message]
    for item in reversed(body.history):
        if item.role == "user":
            pieces.append(item.content)
            if len(pieces) == 3:
                break
    if body.summary:
        pieces.append(body.summary[:400])
    return "\n".join(pieces)[:QUERY_CHARACTERS]
