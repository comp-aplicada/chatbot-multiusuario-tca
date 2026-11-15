"""Rotas da API com o SessionStore real e um LLM falso (PRD, seções 5 e 8.1)."""

import logging
import re
import uuid

import pytest

from app.config import get_settings
from app.errors import LLMTimeout, LLMUnavailable
from app.llm.client import LLMClient
from app.sessions.store import SessionStore

from .conftest import FakeLLM, running_app

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_CHARS = get_settings().message_max_chars


def error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


NOT_FOUND = error("session_not_found", "Sessão não encontrada ou expirada.")
UNAVAILABLE = error(
    "llm_unavailable", "O modelo está indisponível no momento. Tente novamente."
)
TIMEOUT = error(
    "llm_timeout", "O modelo demorou demais para responder. Tente novamente."
)


# GET /api/health


async def test_health_mostra_sessoes_ativas_e_o_modelo_das_configuracoes():
    async with running_app(llm_model="Qwen/Qwen3.8-27B") as api:
        await api.create_session()
        await api.create_session()

        response = await api.client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "active_sessions": 2,
        "model": "Qwen/Qwen3.8-27B",
    }


async def test_health_deixa_de_contar_a_sessao_encerrada(api):
    session_id = await api.create_session()
    await api.client.delete(f"/api/sessions/{session_id}")

    assert (await api.client.get("/api/health")).json()["active_sessions"] == 0


# POST /api/sessions


async def test_criar_sessao_sem_corpo_usa_persona_geral(api):
    response = await api.client.post("/api/sessions")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "persona", "created_at"}
    assert uuid.UUID(body["session_id"]).version == 4
    assert body["persona"] == "geral"
    assert ISO_UTC.match(body["created_at"])


@pytest.mark.parametrize(
    ("payload", "persona"),
    [({}, "geral"), ({"persona": "geral"}, "geral"), ({"persona": "juridico"}, "juridico")],
)
async def test_criar_sessao_com_corpo(api, payload, persona):
    response = await api.client.post("/api/sessions", json=payload)

    assert response.status_code == 201
    assert response.json()["persona"] == persona


async def test_cada_conexao_recebe_um_id_diferente(api):
    ids = {await api.create_session() for _ in range(20)}

    assert len(ids) == 20


async def test_criar_sessao_com_persona_invalida_responde_422(api):
    response = await api.client.post("/api/sessions", json={"persona": "medico"})

    assert response.status_code == 422
    assert response.json() == error(
        "invalid_request",
        "Requisição inválida: persona deve ser 'geral' ou 'juridico'.",
    )
    assert api.app.state.store.count() == 0


# GET /api/sessions/{session_id}


async def test_historico_de_sessao_nova_vem_vazio(api):
    session_id = await api.create_session("juridico")

    response = await api.client.get(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "session_id",
        "persona",
        "created_at",
        "last_activity",
        "messages",
    }
    assert body["session_id"] == session_id
    assert body["persona"] == "juridico"
    assert ISO_UTC.match(body["created_at"])
    assert ISO_UTC.match(body["last_activity"])
    assert body["messages"] == []


async def test_historico_devolve_a_conversa_completa_em_ordem(api):
    session_id = await api.create_session()
    await api.ask(session_id, "primeira")
    await api.ask(session_id, "segunda")

    messages = await api.history(session_id)

    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "primeira"),
        ("assistant", "eco: primeira"),
        ("user", "segunda"),
        ("assistant", "eco: segunda"),
    ]
    for message in messages:
        assert set(message) == {"role", "content", "created_at"}
        assert ISO_UTC.match(message["created_at"])


async def test_ler_o_historico_nao_renova_last_activity(api):
    session_id = await api.create_session()
    session = await api.app.state.store.get(session_id, touch=False)
    before = session.last_activity

    await api.client.get(f"/api/sessions/{session_id}")

    assert session.last_activity == before


@pytest.mark.parametrize("session_id", [str(uuid.uuid4()), "nao-e-um-uuid"])
async def test_historico_de_id_inexistente_responde_404(api, session_id):
    response = await api.client.get(f"/api/sessions/{session_id}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# POST /api/sessions/{session_id}/messages


async def test_pergunta_devolve_a_resposta_do_llm(api):
    session_id = await api.create_session()

    response = await api.ask(session_id, "O que é computação em nuvem?")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"session_id", "reply"}
    assert body["session_id"] == session_id
    assert set(body["reply"]) == {"role", "content", "created_at"}
    assert body["reply"]["role"] == "assistant"
    assert body["reply"]["content"] == "eco: O que é computação em nuvem?"
    assert ISO_UTC.match(body["reply"]["created_at"])


async def test_pergunta_e_gravada_sem_espacos_nas_pontas(api):
    session_id = await api.create_session()

    await api.ask(session_id, "  Olá \n")

    assert api.llm.calls[0].question == "Olá"
    assert (await api.history(session_id))[0]["content"] == "Olá"


async def test_llm_recebe_a_persona_da_sessao(api):
    geral = await api.create_session("geral")
    juridico = await api.create_session("juridico")

    await api.ask(geral, "a")
    await api.ask(juridico, "b")

    assert [call.persona for call in api.llm.calls] == ["geral", "juridico"]


async def test_llm_recebe_o_historico_da_propria_sessao(api):
    a = await api.create_session()
    b = await api.create_session()
    await api.ask(a, "Meu nome é Aurélio.")
    await api.ask(b, "Meu nome é Benedita.")

    await api.ask(a, "Qual é o meu nome?")

    assert api.llm.calls[-1].history == [
        ("user", "Meu nome é Aurélio."),
        ("assistant", "eco: Meu nome é Aurélio."),
    ]


async def test_pergunta_renova_last_activity(api):
    session_id = await api.create_session()
    session = await api.app.state.store.get(session_id, touch=False)
    before = session.last_activity

    await api.ask(session_id, "oi")

    assert session.last_activity > before


async def test_data_da_pergunta_e_a_do_recebimento_e_nao_a_da_resposta():
    async with running_app(FakeLLM(delay=0.2)) as api:
        session_id = await api.create_session()
        await api.ask(session_id, "oi")

        session = await api.app.state.store.get(session_id, touch=False)

    user, assistant = session.messages
    assert (assistant.created_at - user.created_at).total_seconds() >= 0.2


@pytest.mark.parametrize("session_id", [str(uuid.uuid4()), "nao-e-um-uuid"])
async def test_pergunta_em_id_inexistente_responde_404(api, session_id):
    response = await api.ask(session_id, "oi")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert api.llm.calls == []


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"content": ""}, "Requisição inválida: content não pode ficar vazio."),
        ({"content": "  \n "}, "Requisição inválida: content não pode ficar vazio."),
        (
            {"content": "a" * (MAX_CHARS + 1)},
            f"Requisição inválida: content deve ter no máximo {MAX_CHARS} caracteres.",
        ),
        ({}, "Requisição inválida: content é obrigatório."),
    ],
)
async def test_pergunta_invalida_responde_422_e_nao_chama_o_llm(api, payload, message):
    session_id = await api.create_session()

    response = await api.client.post(
        f"/api/sessions/{session_id}/messages", json=payload
    )

    assert response.status_code == 422
    assert response.json() == error("invalid_request", message)
    assert api.llm.calls == []
    assert await api.history(session_id) == []


async def test_pergunta_com_o_tamanho_maximo_e_aceita(api):
    session_id = await api.create_session()

    response = await api.ask(session_id, "a" * MAX_CHARS)

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("exc", "status", "body"),
    [
        (LLMUnavailable(), 503, UNAVAILABLE),
        (LLMTimeout(), 504, TIMEOUT),
        (
            RuntimeError("detalhe interno"),
            500,
            error("internal_error", "Erro interno do servidor."),
        ),
    ],
)
async def test_falha_do_llm_responde_o_erro_do_contrato_e_nao_grava_nada(
    exc, status, body
):
    async with running_app(FakeLLM(error=exc)) as api:
        session_id = await api.create_session()

        response = await api.ask(session_id, "oi")

        assert response.status_code == status
        assert response.json() == body
        assert "detalhe interno" not in response.text
        assert await api.history(session_id) == []


async def test_sessao_continua_funcionando_depois_de_uma_falha_do_llm(api):
    session_id = await api.create_session()
    api.llm.error = LLMUnavailable()
    await api.ask(session_id, "falhou")
    api.llm.error = None

    response = await api.ask(session_id, "de novo")

    assert response.status_code == 200
    assert [m["content"] for m in await api.history(session_id)] == [
        "de novo",
        "eco: de novo",
    ]


# DELETE /api/sessions/{session_id}


async def test_encerrar_sessao_responde_204_sem_corpo(api):
    session_id = await api.create_session()

    response = await api.client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 204
    assert response.content == b""


async def test_sessao_encerrada_passa_a_responder_404(api):
    session_id = await api.create_session()
    await api.client.delete(f"/api/sessions/{session_id}")

    assert (await api.client.get(f"/api/sessions/{session_id}")).json() == NOT_FOUND
    assert (await api.ask(session_id, "oi")).json() == NOT_FOUND
    again = await api.client.delete(f"/api/sessions/{session_id}")
    assert again.status_code == 404
    assert again.json() == NOT_FOUND


@pytest.mark.parametrize("session_id", [str(uuid.uuid4()), "nao-e-um-uuid"])
async def test_encerrar_id_inexistente_responde_404(api, session_id):
    response = await api.client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# Lifespan, expiração e limite


async def test_lifespan_cria_uma_instancia_do_store_e_do_cliente_do_llm():
    async with running_app(override_llm=False) as api:
        assert isinstance(api.app.state.store, SessionStore)
        assert isinstance(api.app.state.llm, LLMClient)


async def test_sem_chave_do_llm_o_app_sobe_e_as_perguntas_respondem_503(caplog):
    caplog.set_level(logging.WARNING)
    async with running_app(override_llm=False, llm_api_key="") as api:
        session_id = await api.create_session()

        response = await api.ask(session_id, "oi")

        assert (await api.client.get("/api/health")).status_code == 200
        assert response.status_code == 503
        assert response.json() == UNAVAILABLE
        assert await api.history(session_id) == []

    assert "llm_api_key_missing" in caplog.text


async def test_sessao_expirada_responde_404():
    async with running_app(session_ttl_min=0.001) as api:  # 60 ms
        session_id = await api.create_session()
        await _sleep(0.1)

        response = await api.client.get(f"/api/sessions/{session_id}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_tarefa_de_limpeza_remove_sessoes_expiradas(caplog):
    caplog.set_level(logging.INFO)
    async with running_app(session_ttl_min=0.001, cleanup_interval_s=0.05) as api:
        await api.create_session()
        await api.create_session()
        await _sleep(0.3)

        assert api.app.state.store.count() == 0

    assert "cleanup removed=2" in caplog.text


async def test_limite_de_sessoes_vem_das_configuracoes():
    async with running_app(session_max=2) as api:
        primeira = await api.create_session()
        await api.create_session()
        await api.create_session()

        assert api.app.state.store.count() == 2
        assert (await api.client.get(f"/api/sessions/{primeira}")).status_code == 404


# Logs (PRD, seção 5.7)


async def test_logs_mostram_so_os_8_primeiros_caracteres_do_id(api, caplog):
    caplog.set_level(logging.INFO)
    session_id = await api.create_session("juridico")
    await api.ask(session_id, "oi")
    await api.client.get(f"/api/sessions/{session_id}")
    await api.client.delete(f"/api/sessions/{session_id}")

    short = session_id[:8]
    assert f"session_created sess={short} persona=juridico" in caplog.text
    assert re.search(
        rf"message sess={short} status=200 latency_ms=\d+ attempts=\d+", caplog.text
    )
    assert f"session_deleted sess={short}" in caplog.text
    assert session_id not in caplog.text


@pytest.mark.parametrize(
    ("exc", "status"), [(LLMUnavailable(), 503), (LLMTimeout(), 504)]
)
async def test_log_da_mensagem_registra_o_status_de_erro(caplog, exc, status):
    caplog.set_level(logging.INFO)
    async with running_app(FakeLLM(error=exc)) as api:
        session_id = await api.create_session()
        await api.ask(session_id, "oi")

    assert f"message sess={session_id[:8]} status={status}" in caplog.text


async def test_log_nao_reproduz_id_malformado(api, caplog):
    caplog.set_level(logging.INFO)

    await api.ask("linha1%0Ainjetada sess=abc", "oi")

    assert "injetada" not in caplog.text
    assert "status=404" in caplog.text


# Swagger


async def test_swagger_e_openapi_ficam_sob_api(api):
    docs = await api.client.get("/api/docs")
    openapi = await api.client.get("/api/openapi.json")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert set(openapi.json()["paths"]) == {
        "/api/health",
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/sessions/{session_id}/messages",
    }


async def test_swagger_mostra_os_modelos_e_so_os_erros_do_contrato(api):
    openapi = (await api.client.get("/api/openapi.json")).json()
    paths = openapi["paths"]

    assert set(openapi["components"]["schemas"]) == {
        "SessionCreateRequest",
        "SessionCreated",
        "SessionDetail",
        "MessageOut",
        "MessageRequest",
        "MessageResponse",
        "Health",
        "ErrorBody",
        "ErrorResponse",
    }
    assert set(paths["/api/health"]["get"]["responses"]) == {"200"}
    assert set(paths["/api/sessions"]["post"]["responses"]) == {"201", "422"}
    session = paths["/api/sessions/{session_id}"]
    assert set(session["get"]["responses"]) == {"200", "404"}
    assert set(session["delete"]["responses"]) == {"204", "404"}
    messages = paths["/api/sessions/{session_id}/messages"]["post"]
    assert set(messages["responses"]) == {"200", "404", "422", "503", "504"}


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
