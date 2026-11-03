"""Local BM25 keyword ranking and reciprocal rank fusion, without extra services."""

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.schemas import MAX_CITATIONS

# Common question words add noise to exact feature and product matches.
STOP_WORDS = frozenset('a an the is are for of to and or in what how can i you apa apakah bagaimana berapa bisa saya aku anda untuk yang dan atau di ke dari itu ini dengan punya sudah termasuk kalau'.split())
BM25_K1 = 1.2
BM25_B = 0.75
RRF_CONSTANT = 60
MAX_CANDIDATES = 30
MAX_CONTEXT_CHARACTERS = 8500
MIN_CONTEXT_CHARACTERS = 512


def tokens(text):
    return [word for word in re.findall(r'[^\W_]+', text.casefold()) if word not in STOP_WORDS]


@dataclass(frozen=True)
class SearchOptions:
    mode: str = 'keyword'
    candidates: int = 10
    top_k: int = 3
    rewrite: bool = False
    rerank: bool = False
    max_passages: int = MAX_CITATIONS
    context_characters: int = MAX_CONTEXT_CHARACTERS

    def __post_init__(self):
        if self.mode not in {'vector', 'keyword', 'hybrid'}:
            raise ValueError('RAG_SEARCH_MODE must be vector, keyword, or hybrid.')
        if not 1 <= self.max_passages <= MAX_CITATIONS:
            raise ValueError(f'RAG_MAX_PASSAGES must be between 1 and {MAX_CITATIONS}.')
        if not MIN_CONTEXT_CHARACTERS <= self.context_characters <= MAX_CONTEXT_CHARACTERS:
            raise ValueError(f'RAG_CONTEXT_CHARACTERS must be between {MIN_CONTEXT_CHARACTERS} and {MAX_CONTEXT_CHARACTERS}.')
        if not 1 <= self.top_k <= self.candidates <= MAX_CANDIDATES:
            raise ValueError(f'Retrieval limits must satisfy 1 <= top_k <= candidates <= {MAX_CANDIDATES}.')


class KeywordIndex:
    def __init__(self, chunks):
        # Omit the repeated root title, which otherwise matches every chunk.
        self.documents = {cid: Counter(tokens(chunk.section.split(' > ', 1)[-1] + '\n' + chunk.text))
                          for cid, chunk in chunks.items()}
        self.lengths = {cid: sum(words.values()) for cid, words in self.documents.items()}
        self.average = sum(self.lengths.values()) / max(len(self.documents), 1)
        self.frequency = Counter(word for words in self.documents.values() for word in words)

    def rank(self, query):
        scores = {}
        for word in set(tokens(query)):
            frequency = self.frequency[word]
            if not frequency:
                continue
            inverse = math.log(1 + (len(self.documents) - frequency + 0.5) / (frequency + 0.5))
            for cid, words in self.documents.items():
                count = words[word]
                if count:
                    denominator = count + BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[cid] / self.average)
                    scores[cid] = scores.get(cid, 0) + inverse * count * (BM25_K1 + 1) / denominator
        return sorted(scores, key=lambda cid: (-scores[cid], cid))


def fuse(rankings):
    scores = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            scores[cid] = scores.get(cid, 0) + 1 / (RRF_CONSTANT + rank)
    return sorted(scores, key=lambda cid: (-scores[cid], cid))
