"""Testes do stub: as 5 rotas do contrato (PRD, seção 5) com respostas fixas."""

import re
import uuid

import httpx
import pytest

from app.main import app

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NOT_FOUND = {
    "error": {
        "code": "session_not_found",
        "message": "Sessão não encontrada ou expirada.",
    }
}


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def create_session(client: httpx.AsyncClient, **kwargs) -> dict:
    response = await client.post("/api/sessions", **kwargs)
    assert response.status_code == 201
    return response.json()


async def test_health_responde_status_sessoes_e_modelo(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "active_sessions", "model"}
    assert body["status"] == "ok"
    assert isinstance(body["active_sessions"], int)
    assert isinstance(body["model"], str) and body["model"]


async def test_criar_sessao_sem_corpo_usa_persona_geral(client):
    body = await create_session(client)

    assert set(body) == {"session_id", "persona", "created_at"}
    assert uuid.UUID(body["session_id"]).version == 4
    assert body["persona"] == "geral"
    assert ISO_UTC.match(body["created_at"])


async def test_criar_sessao_com_persona_juridico(client):
    body = await create_session(client, json={"persona": "juridico"})

    assert body["persona"] == "juridico"


async def test_cada_sessao_recebe_um_id_diferente(client):
    ids = {(await create_session(client))["session_id"] for _ in range(20)}

    assert len(ids) == 20


async def test_criar_sessao_com_persona_invalida_responde_422(client):
    response = await client.post("/api/sessions", json={"persona": "medico"})

    assert response.status_code == 422


async def test_historico_devolve_duas_mensagens_fixas(client):
    created = await create_session(client, json={"persona": "juridico"})

    response = await client.get(f"/api/sessions/{created['session_id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "session_id",
        "persona",
        "created_at",
        "last_activity",
        "messages",
    }
    assert body["session_id"] == created["session_id"]
    assert body["persona"] == "juridico"
    assert ISO_UTC.match(body["created_at"])
    assert ISO_UTC.match(body["last_activity"])
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    for message in body["messages"]:
        assert set(message) == {"role", "content", "created_at"}
        assert message["content"]
        assert ISO_UTC.match(message["created_at"])


async def test_pergunta_responde_com_eco(client):
    created = await create_session(client)

    response = await client.post(
        f"/api/sessions/{created['session_id']}/messages",
        json={"content": "O que é computação em nuvem?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"session_id", "reply"}
    assert body["session_id"] == created["session_id"]
    assert set(body["reply"]) == {"role", "content", "created_at"}
    assert body["reply"]["role"] == "assistant"
    assert body["reply"]["content"] == "eco: O que é computação em nuvem?"
    assert ISO_UTC.match(body["reply"]["created_at"])


async def test_encerrar_sessao_responde_204_sem_corpo(client):
    created = await create_session(client)

    response = await client.delete(f"/api/sessions/{created['session_id']}")

    assert response.status_code == 204
    assert response.content == b""


async def test_sessao_encerrada_passa_a_responder_404(client):
    created = await create_session(client)
    await client.delete(f"/api/sessions/{created['session_id']}")

    response = await client.get(f"/api/sessions/{created['session_id']}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("session_id", [str(uuid.uuid4()), "nao-e-um-uuid"])
@pytest.mark.parametrize(
    ("method", "suffix", "payload"),
    [
        ("GET", "", None),
        ("POST", "/messages", {"content": "oi"}),
        ("DELETE", "", None),
    ],
)
async def test_id_que_nao_foi_criado_responde_404_no_formato_padrao(
    client, session_id, method, suffix, payload
):
    response = await client.request(
        method, f"/api/sessions/{session_id}{suffix}", json=payload
    )

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_health_conta_as_sessoes_criadas(client):
    before = (await client.get("/api/health")).json()["active_sessions"]
    await create_session(client)

    after = (await client.get("/api/health")).json()["active_sessions"]

    assert after == before + 1


async def test_swagger_e_openapi_ficam_sob_api(client):
    docs = await client.get("/api/docs")
    openapi = await client.get("/api/openapi.json")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert openapi.status_code == 200
    assert set(openapi.json()["paths"]) == {
        "/api/health",
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/sessions/{session_id}/messages",
    }
