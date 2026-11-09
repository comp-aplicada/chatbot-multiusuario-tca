import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx

from app.errors import LLMTimeout, LLMUnavailable
from app.llm.client import LLMClient, clean_reply
from app.llm.personas import PERSONAS

BASE_URL = "https://llm.test/v1"
COMPLETIONS = f"{BASE_URL}/chat/completions"


@dataclass
class FakeSettings:
    llm_base_url: str = BASE_URL
    llm_api_key: str = "chave-de-teste"
    llm_model: str = "qwen/qwen3.8-27b"
    llm_extra_body: dict[str, Any] = field(
        default_factory=lambda: {"reasoning_effort": "none"}
    )
    llm_timeout_s: float = 20
    llm_max_retries: int = 2
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    history_window: int = 20


@dataclass
class Msg:
    role: str
    content: str


def completion(content: str | None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen/qwen3.8-27b",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
        },
    )


def error(status: int) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": f"erro {status}"}})


class SleepSpy:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def sleep() -> SleepSpy:
    return SleepSpy()


def make_client(sleep: SleepSpy, **overrides: Any) -> LLMClient:
    return LLMClient(FakeSettings(**overrides), sleep=sleep)


@pytest.fixture
def mock_llm():
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        yield router.post(COMPLETIONS)


def sent_body(route: respx.Route, index: int = -1) -> dict[str, Any]:
    return json.loads(route.calls[index].request.content)


# Contexto


@pytest.mark.parametrize("persona", ["geral", "juridico"])
async def test_contexto_usa_system_prompt_da_persona(mock_llm, sleep, persona):
    mock_llm.mock(return_value=completion("Oi!"))

    await make_client(sleep).chat(persona, [], "Olá")

    messages = sent_body(mock_llm)["messages"]
    assert messages[0] == {"role": "system", "content": PERSONAS[persona]}
    assert messages[-1] == {"role": "user", "content": "Olá"}


async def test_contexto_envia_so_as_ultimas_history_window_mensagens(mock_llm, sleep):
    mock_llm.mock(return_value=completion("ok"))
    history = [Msg("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(6)]

    await make_client(sleep, history_window=4).chat("geral", history, "pergunta")

    messages = sent_body(mock_llm)["messages"]
    assert [m["content"] for m in messages[1:-1]] == ["m2", "m3", "m4", "m5"]
    assert [m["role"] for m in messages[1:-1]] == ["user", "assistant"] * 2
    assert len(messages) == 1 + 4 + 1


async def test_contexto_com_history_window_zero_nao_envia_historico(mock_llm, sleep):
    mock_llm.mock(return_value=completion("ok"))

    await make_client(sleep, history_window=0).chat("geral", [Msg("user", "a")], "b")

    assert len(sent_body(mock_llm)["messages"]) == 2


async def test_parametros_vem_das_configuracoes(mock_llm, sleep):
    mock_llm.mock(return_value=completion("ok"))

    await make_client(sleep, llm_temperature=0.2, llm_max_tokens=256).chat(
        "geral", [], "x"
    )

    body = sent_body(mock_llm)
    assert body["model"] == "qwen/qwen3.8-27b"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 256
    assert body["reasoning_effort"] == "none"  # vindo do extra_body


# Retry e mapeamento de erros


async def test_429_seguido_de_200_resulta_em_sucesso(mock_llm, sleep):
    mock_llm.side_effect = [error(429), completion("Resposta")]

    reply = await make_client(sleep).chat("geral", [], "x")

    assert reply == "Resposta"
    assert mock_llm.call_count == 2
    assert sleep.calls == [1]


async def test_tres_429_levantam_llm_unavailable(mock_llm, sleep):
    mock_llm.side_effect = [error(429), error(429), error(429)]

    with pytest.raises(LLMUnavailable):
        await make_client(sleep).chat("geral", [], "x")

    assert mock_llm.call_count == 3
    assert sleep.calls == [1, 2]


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_5xx_tem_retry(mock_llm, sleep, status):
    mock_llm.side_effect = [error(status), completion("ok")]

    assert await make_client(sleep).chat("geral", [], "x") == "ok"
    assert mock_llm.call_count == 2


async def test_erro_de_conexao_tem_retry(mock_llm, sleep):
    mock_llm.side_effect = [httpx.ConnectError("falhou"), completion("ok")]

    assert await make_client(sleep).chat("geral", [], "x") == "ok"
    assert mock_llm.call_count == 2


async def test_max_retries_zero_nao_repete(mock_llm, sleep):
    mock_llm.side_effect = [error(429)]

    with pytest.raises(LLMUnavailable):
        await make_client(sleep, llm_max_retries=0).chat("geral", [], "x")

    assert mock_llm.call_count == 1
    assert sleep.calls == []


async def test_timeout_levanta_llm_timeout_sem_retry(mock_llm, sleep):
    mock_llm.side_effect = httpx.ReadTimeout("demorou")

    with pytest.raises(LLMTimeout):
        await make_client(sleep).chat("geral", [], "x")

    assert mock_llm.call_count == 1
    assert sleep.calls == []


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_outros_4xx_levantam_llm_unavailable_sem_retry(
    mock_llm, sleep, status, caplog
):
    mock_llm.side_effect = [error(status)]

    with pytest.raises(LLMUnavailable):
        await make_client(sleep).chat("geral", [], "x")

    assert mock_llm.call_count == 1
    assert sleep.calls == []
    assert f"status={status}" in caplog.text
    assert f"erro {status}" in caplog.text


# Limpeza do <think>


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<think>pensando...</think>\n\nOlá!", "Olá!"),
        ("<think>linha 1\nlinha 2</think>Resposta", "Resposta"),
        ("Antes <think>a</think> meio <think>b</think> fim", "Antes  meio  fim"),
        ("Resposta parcial <think>sem fechar\nnunca fecha", "Resposta parcial"),
        ("  sem think  ", "sem think"),
    ],
)
def test_clean_reply(raw, expected):
    assert clean_reply(raw) == expected


async def test_remove_think_da_resposta(mock_llm, sleep):
    mock_llm.mock(return_value=completion("<think>\nhmm\n</think>\n\nOlá!"))

    assert await make_client(sleep).chat("geral", [], "x") == "Olá!"


@pytest.mark.parametrize(
    "content", ["", "   ", "<think>só pensamento</think>", "<think>sem fim", None]
)
async def test_resposta_vazia_levanta_llm_unavailable(mock_llm, sleep, content):
    mock_llm.mock(return_value=completion(content))

    with pytest.raises(LLMUnavailable):
        await make_client(sleep).chat("geral", [], "x")

    assert mock_llm.call_count == 1
