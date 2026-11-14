"""Modelos Pydantic do contrato (PRD, seção 5)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    ErrorResponse,
    Health,
    MessageOut,
    MessageRequest,
    MessageResponse,
    SessionCreated,
    SessionCreateRequest,
    SessionDetail,
)

MAX_CHARS = get_settings().message_max_chars
QUANDO = datetime(2026, 11, 11, 14, 0, 0, 987654, tzinfo=timezone.utc)


def test_requisicao_de_sessao_sem_persona_usa_geral():
    assert SessionCreateRequest().persona == "geral"


@pytest.mark.parametrize("persona", ["geral", "juridico"])
def test_requisicao_de_sessao_aceita_as_personas_do_contrato(persona):
    assert SessionCreateRequest(persona=persona).persona == persona


def test_requisicao_de_sessao_recusa_persona_desconhecida():
    with pytest.raises(ValidationError):
        SessionCreateRequest(persona="medico")


def test_pergunta_e_gravada_sem_espacos_nas_pontas():
    assert MessageRequest(content="  Olá, tudo bem?\n").content == "Olá, tudo bem?"


@pytest.mark.parametrize("content", ["", "   ", "\n\t "])
def test_pergunta_vazia_depois_do_strip_e_recusada(content):
    with pytest.raises(ValidationError):
        MessageRequest(content=content)


def test_pergunta_com_o_tamanho_maximo_e_aceita():
    assert len(MessageRequest(content="a" * MAX_CHARS).content) == MAX_CHARS


def test_pergunta_acima_do_tamanho_maximo_e_recusada():
    with pytest.raises(ValidationError):
        MessageRequest(content="a" * (MAX_CHARS + 1))


def test_tamanho_da_pergunta_e_medido_depois_do_strip():
    content = "  " + "a" * MAX_CHARS + "  "

    assert len(MessageRequest(content=content).content) == MAX_CHARS


def test_datas_saem_em_iso_8601_utc_com_z_e_sem_fracao():
    created = SessionCreated(session_id="abc", persona="geral", created_at=QUANDO)

    assert created.model_dump(mode="json")["created_at"] == "2026-11-11T14:00:00Z"


def test_data_em_outro_fuso_e_convertida_para_utc():
    brasilia = timezone(timedelta(hours=-3))
    message = MessageOut(
        role="user",
        content="oi",
        created_at=datetime(2026, 11, 11, 11, 0, 0, tzinfo=brasilia),
    )

    assert message.model_dump(mode="json")["created_at"] == "2026-11-11T14:00:00Z"


def test_detalhe_da_sessao_tem_os_campos_do_contrato():
    detail = SessionDetail(
        session_id="abc",
        persona="juridico",
        created_at=QUANDO,
        last_activity=QUANDO,
        messages=[MessageOut(role="user", content="oi", created_at=QUANDO)],
    )

    assert detail.model_dump(mode="json") == {
        "session_id": "abc",
        "persona": "juridico",
        "created_at": "2026-11-11T14:00:00Z",
        "last_activity": "2026-11-11T14:00:00Z",
        "messages": [
            {"role": "user", "content": "oi", "created_at": "2026-11-11T14:00:00Z"}
        ],
    }


def test_resposta_da_pergunta_tem_os_campos_do_contrato():
    response = MessageResponse(
        session_id="abc",
        reply=MessageOut(role="assistant", content="olá", created_at=QUANDO),
    )

    assert response.model_dump(mode="json") == {
        "session_id": "abc",
        "reply": {
            "role": "assistant",
            "content": "olá",
            "created_at": "2026-11-11T14:00:00Z",
        },
    }


def test_health_tem_os_campos_do_contrato():
    health = Health(active_sessions=3, model="qwen/qwen3.8-27b")

    assert health.model_dump(mode="json") == {
        "status": "ok",
        "active_sessions": 3,
        "model": "qwen/qwen3.8-27b",
    }


def test_erro_tem_o_formato_padrao():
    error = ErrorResponse(error={"code": "session_not_found", "message": "x"})

    assert error.model_dump(mode="json") == {
        "error": {"code": "session_not_found", "message": "x"}
    }


def test_datas_aparecem_como_date_time_no_swagger():
    schema = SessionCreated.model_json_schema(mode="serialization")

    assert schema["properties"]["created_at"]["type"] == "string"
    assert schema["properties"]["created_at"]["format"] == "date-time"
