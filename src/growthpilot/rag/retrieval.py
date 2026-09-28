from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from growthpilot.rag.embeddings import EmbeddingModel


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    source: str
    score: float


def chunk_text(text: str, *, words: int = 180, overlap: int = 30) -> list[str]:
    tokens = text.split()
    if words <= overlap:
        raise ValueError("words must be greater than overlap")
    return [
        " ".join(tokens[start : start + words])
        for start in range(0, len(tokens), words - overlap)
        if tokens[start : start + words]
    ]


class InMemoryRetriever:
    def __init__(self, embedding_model: EmbeddingModel | None = None):
        self.embedding_model = embedding_model or EmbeddingModel()
        self.contents: list[str] = []
        self.sources: list[str] = []
        self.embeddings = np.empty((0, self.embedding_model.dimensions), dtype=np.float32)

    def add(self, *, source: str, content: str) -> None:
        chunks = chunk_text(content)
        embeddings = self.embedding_model.encode(chunks)
        self.contents.extend(chunks)
        self.sources.extend([source] * len(chunks))
        self.embeddings = np.vstack([self.embeddings, embeddings])

    def search(self, query: str, k: int = 4) -> list[RetrievedChunk]:
        if not self.contents:
            return []
        vector = self.embedding_model.encode([query])[0]
        scores = self.embeddings @ vector
        indices = np.argsort(scores)[::-1][:k]
        return [
            RetrievedChunk(
                self.contents[index], self.sources[index], round(float(scores[index]), 6)
            )
            for index in indices
        ]
