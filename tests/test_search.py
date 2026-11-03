import asyncio

import pytest

from app import rag
from app.search import KeywordIndex, SearchOptions, fuse, tokens
from tests.test_rag import FakeEmbedder, FIXTURE


def test_keyword_ranking_prefers_specific_term_and_does_not_repeat_query_votes():
    chunks = {
        'firebase': rag.Chunk('firebase', 'Demo', 'Demo > Login', 'Firebase Authorized Domains', 'v1', []),
        'plans': rag.Chunk('plans', 'Demo', 'Demo > Plans', 'Gold Silver Bronze', 'v1', []),
    }
    index = KeywordIndex(chunks)
    assert index.rank('Bagaimana Firebase?') == ['firebase']
    assert index.rank('Firebase Firebase') == index.rank('Firebase')
    assert index.rank('unmatchedxyz') == []
    assert tokens('APk / AAB?') == ['apk', 'aab']


def test_fusion_promotes_agreement_and_is_deterministic():
    assert fuse([['a', 'b'], ['c', 'b']])[0] == 'b'
    assert fuse([[], []]) == []
    assert len(fuse([['a'], ['a']])) == 1


@pytest.mark.parametrize('options', [dict(mode='invalid'), dict(top_k=0), dict(candidates=31), dict(top_k=5, candidates=3)])
def test_search_options_validate_bounds(options):
    with pytest.raises(ValueError):
        SearchOptions(**options)


def test_keyword_mode_needs_no_embedding_and_preserves_context_limits(tmp_path):
    async def run():
        source = tmp_path / 'source.md'
        source.write_text(FIXTURE.read_text())
        config = rag.RagConfig(source, tmp_path / 'index.sqlite3', 'fake', 4)
        embedder = FakeEmbedder()
        await rag.ingest(config, embedder)
        embedder.fail = True
        retriever = rag.Retriever(config, embedder, SearchOptions(mode='keyword'))
        result = await retriever.retrieve('Gold formulir')
        assert any('Silver' in chunk.section for chunk in result.chunks)
        assert len({chunk.id for chunk in result.chunks}) == len(result.chunks)
        assert len(result.context()) <= rag.MAX_CONTEXT_CHARACTERS
        assert len(result.chunks) <= rag.MAX_PASSAGES
        assert not (await retriever.retrieve('unmatchedxyz')).chunks
    asyncio.run(run())
