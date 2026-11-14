"""Configurações lidas do .env (PRD, seção 7.1)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

LLM_VARS = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_EXTRA_BODY",
    "LLM_TIMEOUT_S",
    "LLM_TOTAL_TIMEOUT_S",
    "LLM_MAX_RETRIES",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "SESSION_TTL_MIN",
    "SESSION_MAX",
    "HISTORY_WINDOW",
    "MESSAGE_MAX_CHARS",
]


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for name in LLM_VARS:
        monkeypatch.delenv(name, raising=False)


def test_valores_padrao_sao_os_da_tabela_do_prd():
    settings = Settings(_env_file=None)

    assert settings.llm_base_url == "https://api.groq.com/openai/v1"
    assert settings.llm_api_key == ""
    assert settings.llm_model == "qwen/qwen3.8-27b"
    assert settings.llm_extra_body == {"reasoning_effort": "none"}
    assert settings.llm_timeout_s == 20
    assert settings.llm_total_timeout_s == 60
    assert settings.llm_max_retries == 2
    assert settings.llm_max_tokens == 1024
    assert settings.llm_temperature == 0.7
    assert settings.session_ttl_min == 30
    assert settings.session_max == 1000
    assert settings.history_window == 20
    assert settings.message_max_chars == 2000


def test_variaveis_de_ambiente_sobrescrevem_o_padrao(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen3.8-27B")
    monkeypatch.setenv("SESSION_TTL_MIN", "1")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.2")

    settings = Settings(_env_file=None)

    assert settings.llm_model == "Qwen/Qwen3.8-27B"
    assert settings.session_ttl_min == 1
    assert settings.llm_temperature == 0.2


def test_llm_extra_body_e_lido_como_json(monkeypatch):
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"reasoning_effort":"low","top_k":20}')

    settings = Settings(_env_file=None)

    assert settings.llm_extra_body == {"reasoning_effort": "low", "top_k": 20}


def test_llm_extra_body_vazio_desliga_o_parametro_extra(monkeypatch):
    monkeypatch.setenv("LLM_EXTRA_BODY", "{}")

    assert Settings(_env_file=None).llm_extra_body == {}


def test_cada_settings_tem_o_proprio_extra_body():
    a, b = Settings(_env_file=None), Settings(_env_file=None)

    a.llm_extra_body["outro"] = 1

    assert b.llm_extra_body == {"reasoning_effort": "none"}


def test_llm_extra_body_que_nao_e_json_e_recusado(monkeypatch):
    monkeypatch.setenv("LLM_EXTRA_BODY", "reasoning_effort=none")

    with pytest.raises(Exception) as excinfo:
        Settings(_env_file=None)

    assert "llm_extra_body" in str(excinfo.value).lower()


def test_le_o_arquivo_env_no_formato_do_env_example(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comentário\n"
        "LLM_BASE_URL=https://api.deepinfra.com/v1/openai\n"
        "LLM_API_KEY=chave-de-teste\n"
        "LLM_MODEL=Qwen/Qwen3.8-27B\n"
        'LLM_EXTRA_BODY={"reasoning_effort":"none"}\n'
        "SESSION_MAX=5\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.llm_base_url == "https://api.deepinfra.com/v1/openai"
    assert settings.llm_api_key == "chave-de-teste"
    assert settings.llm_model == "Qwen/Qwen3.8-27B"
    assert settings.llm_extra_body == {"reasoning_effort": "none"}
    assert settings.session_max == 5
    assert settings.history_window == 20


def test_variavel_desconhecida_no_env_e_ignorada(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OUTRA_COISA=1\n", encoding="utf-8")

    assert Settings(_env_file=env_file).session_max == 1000


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SESSION_MAX", "0"),
        ("SESSION_TTL_MIN", "0"),
        ("MESSAGE_MAX_CHARS", "0"),
        ("LLM_TIMEOUT_S", "0"),
        ("LLM_TOTAL_TIMEOUT_S", "-1"),
        ("LLM_MAX_RETRIES", "-1"),
        ("HISTORY_WINDOW", "-1"),
    ],
)
def test_valores_sem_sentido_sao_recusados(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
