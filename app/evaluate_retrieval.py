"""Inspect the selected index against a small source-recall worksheet."""

import asyncio
import json

from dotenv import load_dotenv

from app.knowledge import ROOT
from app.rag import FireworksEmbedder, RagConfig, Retriever


async def main():
    load_dotenv(ROOT / ".env", override=False)
    config = RagConfig.from_environment()
    embedder = FireworksEmbedder(config)
    try:
        retriever = Retriever(config, embedder)
        examples = json.loads((ROOT / "steps" / "03-retrieval-examples.json").read_text())
        for example in examples:
            result = await retriever.retrieve(example["question"])
            sections = [chunk.section for chunk in result.chunks]
            missing = [expected for expected in example["expected_sections"]
                       if not any(expected.casefold() in section.casefold() for section in sections)]
            print(json.dumps({"question":example["question"], "sections":sections, "missing_expected":missing,
                              "context_characters":len(result.context()),
                              "answer_review":example.get("expected_behavior", "Review answer and citations separately.")}, ensure_ascii=False))
    finally:
        await embedder.close()


if __name__ == "__main__":
    asyncio.run(main())
