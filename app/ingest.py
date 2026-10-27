"""Run with: .venv/bin/python -m app.ingest"""

import asyncio
import json

from dotenv import load_dotenv

from app.knowledge import ROOT
from app.rag import FireworksEmbedder, RagConfig, ingest


async def main():
    load_dotenv(ROOT / ".env", override=False)
    config = RagConfig.from_environment()
    embedder = FireworksEmbedder(config)
    try:
        print(json.dumps(await ingest(config, embedder), indent=2))
    finally:
        await embedder.close()


if __name__ == "__main__":
    asyncio.run(main())
