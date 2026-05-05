import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)


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
    AZURE_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    AZURE_EMBEDDINGS_API_VERSION: str = os.getenv("AZURE_EMBEDDINGS_API_VERSION", "2024-02-01")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "3072"))

    # Knowledge Base paths
    KB_DIR: Path = Path(os.getenv(
        "KB_DIR",
        str(Path(__file__).parent.parent / "Knowledge Base")
    ))
    MARKDOWN_OUTPUT_DIR: Path = Path(os.getenv(
        "MARKDOWN_OUTPUT_DIR",
        str(Path(__file__).parent.parent / "Knowledge Base" / "markdown_output")
    ))

    # Ingestion settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Supported file extensions
    SUPPORTED_EXTENSIONS: tuple = (".pdf", ".docx", ".doc", ".csv", ".xlsx", ".md", ".mht")
    SKIP_EXTENSIONS: tuple = (".zip", ".py", ".exe", ".png", ".jpg", ".json", ".DS_Store")

    @property
    def db_dsn(self) -> str:
        return (
            f"host={self.DB_HOST} port={self.DB_PORT} "
            f"dbname={self.DB_NAME} user={self.DB_USER} password={self.DB_PASSWORD}"
        )


cfg = Config()
