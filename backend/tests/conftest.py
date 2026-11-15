"""Fixtures dos testes das rotas: app real com um LLM falso no lugar do provedor."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app
from app.routes.sessions import get_llm


@dataclass
class LLMCall:
    persona: str
    history: list[tuple[str, str]]  # (role, content) no momento da chamada
    question: str


@dataclass
class FakeLLM:
    """Devolve "eco: <pergunta>" depois de `delay` segundos, ou levanta `error`."""

    delay: float = 0.0
    error: Exception | None = None
    calls: list[LLMCall] = field(default_factory=list)

    async def chat(self, persona: str, history: Any, question: str) -> str:
        self.calls.append(
            LLMCall(persona, [(m.role, m.content) for m in history], question)
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return f"eco: {question}"


def make_settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **{"llm_api_key": "chave-de-teste", **overrides})


@dataclass
class Running:
    client: httpx.AsyncClient
    app: FastAPI
    llm: FakeLLM

    async def create_session(self, persona: str | None = None) -> str:
        body = {"persona": persona} if persona else None
        response = await self.client.post("/api/sessions", json=body)
        assert response.status_code == 201
        return response.json()["session_id"]

    async def ask(self, session_id: str, content: str) -> httpx.Response:
        return await self.client.post(
            f"/api/sessions/{session_id}/messages", json={"content": content}
        )

    async def history(self, session_id: str) -> list[dict[str, str]]:
        response = await self.client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        return response.json()["messages"]


@asynccontextmanager
async def running_app(
    llm: FakeLLM | None = None,
    *,
    cleanup_interval_s: float = 60,
    override_llm: bool = True,
    **settings: Any,
) -> AsyncIterator[Running]:
    """Sobe o app com lifespan (store, LLMClient e tarefa de limpeza)."""
    llm = llm or FakeLLM()
    app = create_app(make_settings(**settings), cleanup_interval_s=cleanup_interval_s)
    if override_llm:
        app.dependency_overrides[get_llm] = lambda: llm
    async with app.router.lifespan_context(app):
        # raise_app_exceptions=False: o 500 chega como resposta, como no servidor real.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield Running(client=c, app=app, llm=llm)


@pytest.fixture
async def api() -> AsyncIterator[Running]:
    async with running_app() as running:
        yield running
