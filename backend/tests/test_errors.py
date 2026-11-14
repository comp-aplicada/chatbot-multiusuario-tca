"""Formato único de erro (PRD, seção 5.6)."""

import logging

import httpx
import pytest
from fastapi import FastAPI

from app.config import get_settings
from app.errors import (
    LLMTimeout,
    LLMUnavailable,
    SessionNotFound,
    register_error_handlers,
)
from app.schemas import MessageRequest, SessionCreateRequest

MAX_CHARS = get_settings().message_max_chars


def build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/levanta/{name}")
    async def levanta(name: str):
        raise {
            "session": SessionNotFound(),
            "timeout": LLMTimeout(),
            "unavailable": LLMUnavailable(),
            "inesperado": RuntimeError("segredo interno 123"),
        }[name]

    @app.post("/pergunta")
    async def pergunta(body: MessageRequest):
        return {"content": body.content}

    @app.post("/sessao")
    async def sessao(body: SessionCreateRequest | None = None):
        return {"persona": body.persona if body else "geral"}

    return app


@pytest.fixture
async def client():
    # raise_app_exceptions=False: o 500 chega como resposta, como no servidor real.
    transport = httpx.ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize(
    ("name", "status", "code", "message"),
    [
        ("session", 404, "session_not_found", "Sessão não encontrada ou expirada."),
        (
            "timeout",
            504,
            "llm_timeout",
            "O modelo demorou demais para responder. Tente novamente.",
        ),
        (
            "unavailable",
            503,
            "llm_unavailable",
            "O modelo está indisponível no momento. Tente novamente.",
        ),
        ("inesperado", 500, "internal_error", "Erro interno do servidor."),
    ],
)
async def test_excecao_vira_erro_no_formato_padrao(client, name, status, code, message):
    response = await client.get(f"/levanta/{name}")

    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": message}}


async def test_erro_inesperado_loga_o_stack_trace_sem_vazar_para_o_cliente(
    client, caplog
):
    with caplog.at_level(logging.ERROR):
        response = await client.get("/levanta/inesperado")

    assert "segredo interno 123" not in response.text
    assert "RuntimeError" not in response.text
    assert "internal_error" in caplog.text
    assert "RuntimeError: segredo interno 123" in caplog.text
    assert "Traceback" in caplog.text


@pytest.mark.parametrize(
    ("path", "kwargs", "message"),
    [
        (
            "/pergunta",
            {"json": {"content": "   "}},
            "Requisição inválida: content não pode ficar vazio.",
        ),
        (
            "/pergunta",
            {"json": {"content": "a" * (MAX_CHARS + 1)}},
            f"Requisição inválida: content deve ter no máximo {MAX_CHARS} caracteres.",
        ),
        (
            "/pergunta",
            {"json": {}},
            "Requisição inválida: content é obrigatório.",
        ),
        (
            "/pergunta",
            {"json": {"content": 123}},
            "Requisição inválida: content deve ser um texto.",
        ),
        (
            "/pergunta",
            {},
            "Requisição inválida: o corpo da requisição é obrigatório.",
        ),
        (
            "/pergunta",
            {"content": b"{isto nao e json", "headers": {"Content-Type": "application/json"}},
            "Requisição inválida: o corpo não é um JSON válido.",
        ),
        (
            "/sessao",
            {"json": {"persona": "medico"}},
            "Requisição inválida: persona deve ser 'geral' ou 'juridico'.",
        ),
    ],
)
async def test_requisicao_invalida_responde_422_com_o_detalhe_do_campo(
    client, path, kwargs, message
):
    response = await client.post(path, **kwargs)

    assert response.status_code == 422
    assert response.json() == {"error": {"code": "invalid_request", "message": message}}


async def test_erro_de_validacao_sem_traducao_usa_o_texto_do_pydantic(client):
    response = await client.post("/sessao", json=["lista", "no", "lugar", "do", "objeto"])

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["message"].startswith("Requisição inválida: ")
    assert len(error["message"]) > len("Requisição inválida: ")
