from __future__ import annotations

import hashlib
import re

import numpy as np


class EmbeddingModel:
    """Sentence Transformer adapter with an offline deterministic fallback."""

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dimensions: int = 384
    ):
        self.model_name = model_name
        self.dimensions = dimensions
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name, local_files_only=True)
        except (ImportError, OSError):
            self._model = None

    @property
    def backend(self) -> str:
        return "sentence-transformers" if self._model is not None else "hashing-fallback"

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is not None:
            return np.asarray(
                self._model.encode(texts, normalize_embeddings=True), dtype=np.float32
            )
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                value = int.from_bytes(digest, "little")
                matrix[row, value % self.dimensions] += 1.0 if value & 1 else -1.0
            norm = np.linalg.norm(matrix[row])
            if norm:
                matrix[row] /= norm
        return matrix
