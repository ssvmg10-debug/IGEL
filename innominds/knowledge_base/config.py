import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)


def _truthy(raw: str | None, default: bool = False) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # PostgreSQL
    DB_HOST: str = os.getenv("DB_HOST", "192.168.204.65")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "genai")
    DB_USER: str = os.getenv("DB_USER", "genai")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "1234")

    # Azure OpenAI - LLM
    AZURE_API_KEY: str = os.getenv("AZURE_API_KEY", "")
    AZURE_ENDPOINT: str = os.getenv("AZURE_ENDPOINT", "")
    AZURE_DEPLOYMENT: str = os.getenv("AZURE_DEPLOYMENT", "gpt-4.1")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")

    # Azure OpenAI - Embeddings
    AZURE_EMBEDDING_DEPLOYMENT: str = os.getenv(
        "AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
    )
    AZURE_EMBEDDINGS_API_VERSION: str = os.getenv(
        "AZURE_EMBEDDINGS_API_VERSION", "2024-02-01"
    )
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "3072"))

    # Knowledge Base paths
    KB_DIR: Path = Path(
        os.getenv(
            "KB_DIR",
            str(Path(__file__).parent.parent / "Knowledge Base"),
        )
    )
    MARKDOWN_OUTPUT_DIR: Path = Path(
        os.getenv(
            "MARKDOWN_OUTPUT_DIR",
            str(Path(__file__).parent.parent / "Knowledge Base" / "markdown_output"),
        )
    )

    # Ingestion settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Supported file extensions
    SUPPORTED_EXTENSIONS: tuple[str, ...] = (
        ".pdf",
        ".docx",
        ".doc",
        ".csv",
        ".xlsx",
        ".md",
        ".mht",
    )
    SKIP_EXTENSIONS: tuple[str, ...] = (
        ".zip",
        ".py",
        ".exe",
        ".png",
        ".jpg",
        ".json",
        ".DS_Store",
    )

    # ── V3 Retrieval / rerank / GraphRAG ───────────────────────────────────
    RERANKER_BACKEND: str = os.getenv("RERANKER_BACKEND", "none").strip().lower()
    RERANKER_MODEL: str = os.getenv(
        "RERANKER_MODEL",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    RERANKER_TOP_N: int = int(os.getenv("RERANKER_TOP_N", "48"))
    RERANKER_SCORE_THRESHOLD: float = float(os.getenv("RERANKER_SCORE_THRESHOLD", "0.2"))
    RETRIEVAL_CANDIDATE_MULTIPLIER: int = int(
        os.getenv("RETRIEVAL_CANDIDATE_MULTIPLIER", "6"),
    )

    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_RERANK_MODEL: str = os.getenv(
        "COHERE_RERANK_MODEL",
        "rerank-english-v3.0",
    )

    KG_ENABLED: bool = _truthy(os.getenv("KG_ENABLED"), True)
    KG_MAX_HOPS: int = min(3, max(0, int(os.getenv("KG_MAX_HOPS", "2"))))
    CONTEXT_INCLUDE_IMAGES: bool = _truthy(os.getenv("CONTEXT_INCLUDE_IMAGES"), True)

    CONTEXT_TOKEN_BUDGET: int = int(os.getenv("CONTEXT_TOKEN_BUDGET", "8000"))
    CONTEXT_RESERVE_PROMPT: int = int(os.getenv("CONTEXT_RESERVE_PROMPT", "800"))
    _raw_ms = os.getenv("CONTEXT_MIN_SCORE")
    if _raw_ms is None or str(_raw_ms).strip() == "":
        CONTEXT_MIN_SCORE: float | None = None
    else:
        CONTEXT_MIN_SCORE = float(_raw_ms)
    CONTEXT_MAX_CHUNKS: int = int(os.getenv("CONTEXT_MAX_CHUNKS", "10"))
    CONTEXT_KG_BUDGET_RATIO: float = float(os.getenv("CONTEXT_KG_BUDGET_RATIO", "0.22"))
    CONTEXT_IMAGE_BUDGET_RATIO: float = float(
        os.getenv("CONTEXT_IMAGE_BUDGET_RATIO", "0.08"),
    )

    GENERATION_RUNS_LOGGING: bool = _truthy(os.getenv("GENERATION_RUNS_LOGGING"), False)

    @property
    def db_dsn(self) -> str:
        return (
            f"host={self.DB_HOST} port={self.DB_PORT} "
            f"dbname={self.DB_NAME} user={self.DB_USER} password={self.DB_PASSWORD}"
        )


cfg = Config()
