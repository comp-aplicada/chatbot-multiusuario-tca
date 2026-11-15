"""Configurações da aplicação, lidas do .env (PRD, seção 7.1).

O .env fica na raiz do repositório (o mesmo que o Docker Compose usa) e nunca
é versionado. Variáveis de ambiente têm prioridade sobre o arquivo.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provedor do LLM (API compatível com a OpenAI)
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen/qwen3.8-27b"
    # JSON repassado como extra_body. O padrão desliga o raciocínio do Qwen3.8;
    # use {} só para um modelo que não aceite o parâmetro.
    llm_extra_body: dict[str, Any] = Field(
        default_factory=lambda: {"reasoning_effort": "none"}
    )

    # Timeouts e retries
    llm_timeout_s: float = Field(default=20, gt=0)
    llm_total_timeout_s: float = Field(default=60, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)

    # Geração
    llm_max_tokens: int = Field(default=1024, gt=0)
    llm_temperature: float = Field(default=0.7, ge=0)

    # Sessões
    session_ttl_min: float = Field(default=30, gt=0)
    session_max: int = Field(default=1000, gt=0)
    history_window: int = Field(default=20, ge=0)
    message_max_chars: int = Field(default=2000, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
