"""Cliente do LLM (Qwen3) via API compatível com a OpenAI.

O código não testa qual é o provedor: modelo, URL e parâmetros extras vêm só
das configurações (.env). Trocar Groq por DeepInfra é mudar o .env.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.errors import LLMTimeout, LLMUnavailable
from app.llm.personas import PERSONAS

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_UNCLOSED = re.compile(r"<think>.*\Z", re.DOTALL)


class LLMSettings(Protocol):
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_extra_body: dict[str, Any]
    llm_timeout_s: float
    llm_max_retries: int
    llm_max_tokens: int
    llm_temperature: float
    history_window: int


class ChatMessage(Protocol):
    role: str
    content: str


def clean_reply(text: str | None) -> str:
    """Remove blocos <think> (fechados ou não) e espaços nas pontas."""
    text = _THINK_BLOCK.sub("", text or "")
    text = _THINK_UNCLOSED.sub("", text)
    return text.strip()


def _is_retryable(exc: Exception) -> bool:
    # APITimeoutError é subclasse de APIConnectionError e é tratada antes.
    if isinstance(exc, APIConnectionError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._sleep = sleep
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=0,
        )

    def build_messages(
        self, persona: str, history: Sequence[ChatMessage], question: str
    ) -> list[dict[str, str]]:
        """System prompt da persona + últimas HISTORY_WINDOW mensagens + pergunta."""
        window = self._settings.history_window
        recent = list(history)[-window:] if window > 0 else []
        return [
            {"role": "system", "content": PERSONAS[persona]},
            *({"role": m.role, "content": m.content} for m in recent),
            {"role": "user", "content": question},
        ]

    async def chat(
        self, persona: str, history: Sequence[ChatMessage], question: str
    ) -> str:
        """Pergunta ao LLM. Levanta LLMTimeout ou LLMUnavailable."""
        s = self._settings
        messages = self.build_messages(persona, history, question)
        max_attempts = 1 + s.llm_max_retries

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=s.llm_model,
                    messages=messages,
                    temperature=s.llm_temperature,
                    max_tokens=s.llm_max_tokens,
                    extra_body=s.llm_extra_body,
                )
            except APITimeoutError as exc:
                logger.warning("llm_timeout attempt=%d", attempt)
                raise LLMTimeout() from exc
            except (APIConnectionError, APIStatusError) as exc:
                if not _is_retryable(exc):
                    assert isinstance(exc, APIStatusError)
                    logger.error(
                        "llm_error status=%d body=%s",
                        exc.status_code,
                        exc.response.text,
                    )
                    raise LLMUnavailable() from exc
                reason = getattr(exc, "status_code", "connection")
                if attempt == max_attempts:
                    logger.error(
                        "llm_unavailable attempts=%d reason=%s", attempt, reason
                    )
                    raise LLMUnavailable() from exc
                delay = 2 ** (attempt - 1)
                logger.warning(
                    "llm_retry attempt=%d reason=%s wait_s=%d", attempt, reason, delay
                )
                await self._sleep(delay)
                continue

            content = response.choices[0].message.content if response.choices else None
            reply = clean_reply(content)
            if not reply:
                logger.error("llm_empty_reply attempt=%d", attempt)
                raise LLMUnavailable()
            return reply

        raise LLMUnavailable()  # inalcançável: o laço sempre retorna ou levanta
