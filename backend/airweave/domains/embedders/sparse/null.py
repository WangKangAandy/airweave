"""Null sparse embedder that returns no embeddings (for offline use)."""

from airweave.domains.embedders.types import SparseEmbedding


class NullSparseEmbedder:
    """Null sparse embedder that returns no embeddings.

    Use this when network is unavailable and you don't need sparse embeddings.
    """

    @property
    def model_name(self) -> str:
        return "null"

    @property
    def dimensions(self) -> int:
        return 0

    async def embed(self, text: str) -> SparseEmbedding:
        return SparseEmbedding(indices=[], values=[])

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        return [SparseEmbedding(indices=[], values=[]) for _ in texts]

    async def close(self) -> None:
        pass
