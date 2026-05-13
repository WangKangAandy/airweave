"""Local dense embedder satisfying DenseEmbedderProtocol.

Calls a text2vec-transformers inference container over HTTP.
Handles batching, concurrency, input/response validation, and
error translation. Callers pass text, get DenseEmbedding back,
handle errors themselves.
"""

import asyncio

import httpx

from airweave.domains.embedders.exceptions import (
    EmbedderConnectionError,
    EmbedderDimensionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderResponseError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.types import DenseEmbedding

_PROVIDER = "local"


class LocalDenseEmbedder:
    """Local dense embedder satisfying DenseEmbedderProtocol.

    Calls a text2vec-transformers inference container over HTTP.
    Handles batching, concurrency, input/response validation, and
    error translation. Callers pass text, get DenseEmbedding back,
    handle errors themselves.
    """

    _MAX_BATCH_SIZE: int = 64
    _MAX_CONCURRENT_REQUESTS: int = 24
    _CONNECT_TIMEOUT_S: float = 10.0
    _READ_WRITE_TIMEOUT_S: float = 120.0
    _POOL_TIMEOUT_S: float = 120.0
    _MAX_CONNECTIONS: int = 128
    _MAX_KEEPALIVE_CONNECTIONS: int = 48

    def __init__(
        self,
        *,
        inference_url: str,
        dimensions: int,
    ) -> None:
        """Initialize the local dense embedder.

        Args:
            inference_url: Base URL of the text2vec inference container.
            dimensions: Expected output dimensions (validated on response).
        """
        self._inference_url = inference_url
        self._dimensions = dimensions
        timeout = httpx.Timeout(
            connect=self._CONNECT_TIMEOUT_S,
            read=self._READ_WRITE_TIMEOUT_S,
            write=self._READ_WRITE_TIMEOUT_S,
            pool=self._POOL_TIMEOUT_S,
        )
        limits = httpx.Limits(
            max_connections=self._MAX_CONNECTIONS,
            max_keepalive_connections=self._MAX_KEEPALIVE_CONNECTIONS,
        )
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_REQUESTS)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """The model identifier."""
        return "local"

    @property
    def dimensions(self) -> int:
        """The output vector dimensionality."""
        return self._dimensions

    async def embed(self, text: str) -> DenseEmbedding:
        """Embed a single text into a dense vector."""
        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[DenseEmbedding]:
        """Embed a batch of texts into dense vectors."""
        if not texts:
            return []

        self._validate_inputs(texts)

        sub_batches = [
            texts[i : i + self._MAX_BATCH_SIZE] for i in range(0, len(texts), self._MAX_BATCH_SIZE)
        ]

        # Run sub-batches sequentially so many concurrent sync workers do not each
        # schedule N×64 coroutines that contend for the same httpx pool (PoolTimeout).
        nested_results: list[list[DenseEmbedding]] = []
        for batch in sub_batches:
            nested_results.append(await self._embed_sub_batch(batch))

        return [embedding for batch_result in nested_results for embedding in batch_result]

    async def close(self) -> None:
        """Release held resources."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self, texts: list[str]) -> None:
        """Validate all input texts.

        Raises:
            EmbedderInputError: If any text is empty or blank.
        """
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbedderInputError(f"Text at index {i} is empty or blank")

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------

    async def _embed_sub_batch(self, batch: list[str]) -> list[DenseEmbedding]:
        """Embed a sub-batch with one in-flight request per batch (sequential).

        Avoids ``asyncio.gather`` fan-out (64 coroutines per batch) competing for the
        same httpx pool while other sync workers also call ``embed_many``.
        """
        return [await self._embed_single(text) for text in batch]

    async def _embed_single(self, text: str) -> DenseEmbedding:
        """Make a single HTTP call to the inference container.

        Raises:
            EmbedderTimeoutError: On request timeout.
            EmbedderConnectionError: On connection failure.
            EmbedderProviderError: On HTTP error response.
            EmbedderResponseError: On missing 'vector' key.
            EmbedderDimensionError: On dimension mismatch.
        """
        async with self._semaphore:
            try:
                response = await self._client.post(
                    f"{self._inference_url}/vectors",
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as e:
                # PoolTimeout subclasses TimeoutException; branch explicitly so logs/UI
                # never mislabel pool starvation as a generic read timeout.
                if isinstance(e, httpx.PoolTimeout):
                    raise EmbedderTimeoutError(
                        "Local embedding HTTP client pool timed out waiting for a free "
                        f"connection (sync may be too concurrent for current pool size): {e}",
                        provider=_PROVIDER,
                    ) from e
                raise EmbedderTimeoutError(
                    f"Local embedding request timed out: {e}",
                    provider=_PROVIDER,
                ) from e
            except httpx.ConnectError as e:
                raise EmbedderConnectionError(
                    f"Local embedding connection failed: {e}",
                    provider=_PROVIDER,
                ) from e
            except httpx.HTTPStatusError as e:
                raise EmbedderProviderError(
                    f"Local embedding service error (status {e.response.status_code}): "
                    f"{e.response.text}",
                    provider=_PROVIDER,
                    retryable=e.response.status_code >= 500,
                ) from e
            except httpx.RequestError as e:
                raise EmbedderConnectionError(
                    f"Local embedding connection failed: {e}",
                    provider=_PROVIDER,
                ) from e

            if "vector" not in data:
                raise EmbedderResponseError(
                    "Invalid response from local embedding service: missing 'vector' key"
                )

            vector = data["vector"]
            if len(vector) != self._dimensions:
                raise EmbedderDimensionError(
                    expected=self._dimensions,
                    actual=len(vector),
                )

            return DenseEmbedding(vector=vector)
