"""
Azure OpenAI Embeddings — text-embedding-3-large (3072 dims)

Features:
  - Batched embedding (32 texts per API call)
  - Exponential backoff retry on rate-limit / transient errors
  - Returns embeddings as list[list[float]] aligned to input order
"""
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from openai import AzureOpenAI, RateLimitError, APIConnectionError, APITimeoutError
from knowledge_base.config import cfg

logger = logging.getLogger(__name__)

_client: AzureOpenAI | None = None


def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_key=cfg.AZURE_API_KEY,
            azure_endpoint=cfg.AZURE_ENDPOINT,
            api_version=cfg.AZURE_EMBEDDINGS_API_VERSION,
        )
    return _client


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(cfg.MAX_RETRIES),
    reraise=True,
)
def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a single batch (max 32 texts) with retry on transient errors."""
    client = _get_client()
    response = client.embeddings.create(
        model=cfg.AZURE_EMBEDDING_DEPLOYMENT,
        input=texts,
        dimensions=cfg.EMBEDDING_DIM,
    )
    # Response items are ordered by index
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    Embed a list of texts in batches.
    Returns list of embeddings in the same order as input texts.
    Empty or whitespace-only texts get a zero vector.
    """
    results: list[list[float] | None] = [None] * len(texts)
    zero_vector = [0.0] * cfg.EMBEDDING_DIM

    # Separate non-empty texts with their original indices
    to_embed: list[tuple[int, str]] = [
        (i, t.strip()) for i, t in enumerate(texts) if t.strip()
    ]

    for batch_start in range(0, len(to_embed), batch_size):
        batch = to_embed[batch_start:batch_start + batch_size]
        indices = [item[0] for item in batch]
        batch_texts = [item[1] for item in batch]

        try:
            embeddings = _embed_batch(batch_texts)
            for idx, emb in zip(indices, embeddings):
                results[idx] = emb
            logger.debug("Embedded batch %d–%d", batch_start, batch_start + len(batch))
        except Exception as e:
            logger.error("Embedding batch %d–%d failed: %s", batch_start, batch_start + len(batch), e)
            # Fill failed batch with zero vectors rather than crashing ingestion
            for idx in indices:
                results[idx] = zero_vector

        # Small pause between batches to stay within rate limits
        if batch_start + batch_size < len(to_embed):
            time.sleep(0.3)

    # Fill empty/whitespace texts with zero vectors
    return [r if r is not None else zero_vector for r in results]


def embed_single(text: str) -> list[float]:
    """Embed a single text — convenience wrapper for query-time use."""
    if not text.strip():
        return [0.0] * cfg.EMBEDDING_DIM
    return embed_texts([text])[0]


def format_for_pgvector(embedding: list[float]) -> str:
    """Format embedding as PostgreSQL vector literal string."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
