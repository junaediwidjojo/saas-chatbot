import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from app import rag
from app.memory import ConversationMemory

FIXTURE = Path(__file__).resolve().parent.parent / 'knowledge/rag-example.md'


class FakeEmbedder:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def embed(self, texts):
        self.calls.append(texts)
        if self.fail:
            raise RuntimeError('Simulated embedding failure')
        vectors = []
        for text in texts:
            text = text.casefold()
            if 'unrelated astronomy' in text:
                vector = [0, 0, 0, 1]
            else:
                vector = [float('gold' in text), float('silver' in text or 'formulir' in text), 0, 0]
                if not any(vector):
                    vector[2] = 1
            vectors.append(rag.normalize(vector, 4))
        return vectors


@pytest.fixture
def config(tmp_path):
    source = tmp_path / 'knowledge.md'
    source.write_text(FIXTURE.read_text())
    return rag.RagConfig(source, tmp_path / 'index.sqlite3', 'fake-model', 4)


def test_chunk_ids_are_stable_and_keep_plan_dependencies(config):
    before = rag.chunk_document(config.source)
    gold = next(chunk for chunk in before if chunk.section.endswith('Paket Gold'))
    silver = next(chunk for chunk in before if chunk.section.endswith('Paket Silver'))
    assert silver.id in gold.related_ids
    assert '14 hari' in gold.text  # Parent introduction applies to all plans.
    assert all(len(chunk.text) <= rag.CHUNK_CHARACTERS for chunk in before)
    config.source.write_text(config.source.read_text().replace('USD 20', 'USD 21'))
    after = rag.chunk_document(config.source)
    assert [chunk.id for chunk in before] == [chunk.id for chunk in after]
    assert before[0].version != after[0].version


def test_long_sections_are_split_without_losing_tail(config):
    config.source.write_text('# Example\n\n## Long\n\n' + 'x' * (rag.CHUNK_CHARACTERS * 2 + 17))
    chunks = rag.chunk_document(config.source)
    assert len(chunks) == 3
    assert ''.join(chunk.text for chunk in chunks) == 'x' * (rag.CHUNK_CHARACTERS * 2 + 17)


def test_reingestion_reuses_vectors_updates_versions_and_removes_deleted_sections(config):
    async def run():
        embedder = FakeEmbedder()
        first = await rag.ingest(config, embedder)
        second = await rag.ingest(config, embedder)
        assert second['embedded'] == 0 and second['chunks'] == first['chunks']
        config.source.write_text(config.source.read_text().replace('USD 20', 'USD 21'))
        third = await rag.ingest(config, embedder)
        assert third['embedded'] == 1
        assert third['version'] != second['version']
        source = config.source.read_text()
        config.source.write_text(source[:source.index('## Dukungan remote')])
        fourth = await rag.ingest(config, embedder)
        assert fourth['chunks'] < third['chunks']
        with sqlite3.connect(config.index) as db:
            rows = list(db.execute('SELECT id,payload FROM chunks'))
        assert len(rows) == len(set(cid for cid, _ in rows)) == fourth['chunks']
        assert all(json.loads(payload)['version'] == fourth['version'] for _, payload in rows)
    asyncio.run(run())


def test_failed_ingestion_does_not_publish_partial_updates(config):
    async def run():
        embedder = FakeEmbedder()
        before = await rag.ingest(config, embedder)
        config.source.write_text(config.source.read_text().replace('USD 20', 'USD 21'))
        embedder.fail = True
        with pytest.raises(RuntimeError):
            await rag.ingest(config, embedder)
        with sqlite3.connect(config.index) as db:
            metadata = dict(db.execute('SELECT key,value FROM metadata'))
            assert metadata['version'] == before['version']
            assert db.execute('SELECT count(*) FROM chunks').fetchone()[0] == before['chunks']
    asyncio.run(run())


def test_retrieval_has_inheritance_bounded_context_and_abstention(config):
    async def run():
        embedder = FakeEmbedder()
        await rag.ingest(config, embedder)
        retriever = rag.Retriever(config, embedder)
        result = await retriever.retrieve('Apakah Gold punya formulir?')
        assert any(chunk.section.endswith('Paket Gold') for chunk in result.chunks)
        assert any(chunk.section.endswith('Paket Silver') for chunk in result.chunks)
        assert len(result.chunks) <= rag.MAX_PASSAGES
        assert len(result.context()) <= rag.MAX_CONTEXT_CHARACTERS
        assert (await retriever.retrieve('unrelated astronomy')).chunks == []
        config.source.write_text(config.source.read_text() + '\nChanged source.')
        with pytest.raises(rag.RagUnavailable, match='Knowledge changed'):
            await retriever.retrieve('Gold')
    asyncio.run(run())


def test_missing_index_and_configuration_mismatch_require_reingestion(config):
    with pytest.raises(rag.RagUnavailable, match='missing'):
        rag.Retriever(config, FakeEmbedder())
    asyncio.run(rag.ingest(config, FakeEmbedder()))
    changed = rag.RagConfig(config.source, config.index, 'different-model', 4)
    with pytest.raises(rag.RagUnavailable, match='configuration changed'):
        rag.Retriever(changed, FakeEmbedder())


@pytest.mark.parametrize('vector', [[0, 0], [float('nan'), 1], [float('inf'), 1], [1], ['bad', 1]])
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(rag.RagUnavailable):
        rag.normalize(vector, 2)


def test_followup_query_uses_user_context_not_assistant_claims():
    class Request(ConversationMemory):
        message: str
    body = Request(message='Dan formulir?', summary='User is evaluating plans.', history=[
        {'role':'user','content':'Saya tertarik Gold'},
        {'role':'assistant','content':'UNVERIFIED_SECRET_FEATURE'},
    ])
    query = rag.retrieval_query(body)
    assert 'Gold' in query and 'Dan formulir?' in query
    assert 'UNVERIFIED_SECRET_FEATURE' not in query


def test_index_cannot_be_written_to_public_static_directory(monkeypatch):
    monkeypatch.setenv('SAAS_KNOWLEDGE_FILE', str(FIXTURE))
    monkeypatch.setenv('RAG_INDEX_FILE', 'app/static/index.sqlite3')
    with pytest.raises(ValueError, match='outside app/static'):
        rag.RagConfig.from_environment()
