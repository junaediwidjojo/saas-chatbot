import asyncio

import pytest

from app.compare_retrieval import cost_estimate, grade_answer, recall
from app.retrieval_assistant import RetrievalAssistant
from app.rag import Chunk
from app.schemas import ChatResponse
from app.search import SearchOptions


@pytest.mark.parametrize('result', [{'ids': ['invented', 'b']}, {'ids': ['a', 'a']}, {'ids': ['a']}, {'ids': [1, 'b']}, []])
def test_reranking_rejects_unknown_duplicate_missing_and_wrong_type_ids(result):
    async def run():
        assistant = RetrievalAssistant(None)

        async def generate(instructions, payload):
            return result

        assistant.generate = generate
        chunks = [Chunk(cid, 'Demo', cid, 'Evidence', 'v1', []) for cid in ['a', 'b']]
        assert await assistant.rerank('question', chunks) == ['a', 'b']
        assert assistant.events == ['rerank_fallback']
    asyncio.run(run())


def test_valid_reranking_preserves_candidate_identity():
    async def run():
        assistant = RetrievalAssistant(None)

        async def generate(instructions, payload):
            return {'ids': ['b', 'a']}

        assistant.generate = generate
        chunks = [Chunk(cid, 'Demo', cid, 'Evidence', 'v1', []) for cid in ['a', 'b']]
        assert await assistant.rerank('question', chunks) == ['b', 'a']
    asyncio.run(run())


def test_rewriting_keeps_original_constraints_and_falls_back_on_failure():
    async def run():
        assistant = RetrievalAssistant(None)

        async def generate(instructions, payload):
            return {'query': 'Generic product question'}

        assistant.generate = generate
        original = 'Jagel Gold, bukan Platinum; maksimal 1 MB JPG/PNG'
        assert (await assistant.rewrite(original)).startswith(original)

        async def fail(instructions, payload):
            raise TimeoutError()

        assistant.generate = fail
        assert await assistant.rewrite(original) == original
        assert assistant.events == ['rewrite_fallback']
    asyncio.run(run())


@pytest.mark.parametrize('options', [dict(max_passages=0), dict(max_passages=7), dict(context_characters=511), dict(context_characters=8501)])
def test_final_context_options_enforce_hard_limits(options):
    with pytest.raises(ValueError):
        SearchOptions(**options)


def test_recall_does_not_reward_unknown_policy_questions():
    assert recall([], ['Refund']) is None
    assert recall(['Gold', 'Silver'], ['Paket Gold']) == 0.5


def test_cost_requires_reported_usage_and_separates_embeddings_from_chat():
    calls = [dict(endpoint='embedding', usage=dict(prompt_tokens=1000)),
             dict(endpoint='chat', usage=dict(prompt_tokens=1000, completion_tokens=1000))]
    assert cost_estimate(calls) == 0.0016
    assert cost_estimate([dict(endpoint='chat', usage={})]) is None


def test_answer_rubric_does_not_accept_fallback_as_policy_abstention():
    example = dict(must_abstain=True)
    assert grade_answer(example, ChatResponse(intent='unknown', answer='Not documented; contact support.', requires_human=True))['passed']
    assert not grade_answer(example, ChatResponse(intent='fallback', answer='Try support.', requires_human=True))['passed']


def test_reranking_respects_smaller_final_context_and_keeps_chunk_metadata(tmp_path):
    from app import rag
    from tests.test_rag import FakeEmbedder, FIXTURE

    async def run():
        source = tmp_path / 'source.md'
        source.write_text(FIXTURE.read_text())
        config = rag.RagConfig(source, tmp_path / 'index.sqlite3', 'fake', 4)
        embedder = FakeEmbedder()
        embedder.client = None
        await rag.ingest(config, embedder)
        retriever = rag.Retriever(config, embedder, SearchOptions(mode='hybrid', rerank=True, max_passages=1))

        async def generate(instructions, payload):
            return {'ids': [passage['id'] for passage in reversed(payload['passages'])]}

        retriever.assistant.generate = generate
        result = await retriever.retrieve('Gold formulir')
        assert len(result.chunks) == 1
        chunk = result.chunks[0]
        assert chunk is retriever.chunks[chunk.id]
        assert chunk.section and chunk.version and chunk.title
    asyncio.run(run())
