"""Concorrência determinística (PRD, seção 8.1).

Com um LLM falso lento, estes testes provam que sessões diferentes são
atendidas em paralelo, que as respostas não se misturam e que perguntas da
mesma sessão ficam em fila.
"""

import asyncio
import time

from .conftest import FakeLLM, running_app

NOT_FOUND = {
    "error": {
        "code": "session_not_found",
        "message": "Sessão não encontrada ou expirada.",
    }
}
TIMEOUT = {
    "error": {
        "code": "llm_timeout",
        "message": "O modelo demorou demais para responder. Tente novamente.",
    }
}


async def test_10_sessoes_em_paralelo_nao_sao_serializadas_nem_se_misturam():
    async with running_app(FakeLLM(delay=1)) as api:
        ids = [await api.create_session() for _ in range(10)]

        start = time.perf_counter()
        responses = await asyncio.gather(
            *(api.ask(sid, f"pergunta da sessão {i}") for i, sid in enumerate(ids))
        )
        elapsed = time.perf_counter() - start

        # Em série seriam 10 s. Em paralelo, perto de 1 s.
        assert elapsed < 3
        for i, (sid, response) in enumerate(zip(ids, responses)):
            assert response.status_code == 200
            body = response.json()
            assert body["session_id"] == sid
            assert body["reply"]["content"] == f"eco: pergunta da sessão {i}"
            assert [m["content"] for m in await api.history(sid)] == [
                f"pergunta da sessão {i}",
                f"eco: pergunta da sessão {i}",
            ]


async def test_perguntas_simultaneas_na_mesma_sessao_ficam_em_fila():
    async with running_app(FakeLLM(delay=0.2)) as api:
        session_id = await api.create_session()

        first = asyncio.create_task(api.ask(session_id, "primeira"))
        await asyncio.sleep(0.05)  # garante que a primeira pegou o lock
        second = asyncio.create_task(api.ask(session_id, "segunda"))
        responses = await asyncio.gather(first, second)

        assert [r.status_code for r in responses] == [200, 200]
        messages = await api.history(session_id)
        assert [(m["role"], m["content"]) for m in messages] == [
            ("user", "primeira"),
            ("assistant", "eco: primeira"),
            ("user", "segunda"),
            ("assistant", "eco: segunda"),
        ]
        # A 2ª chamada ao LLM já recebe a 1ª troca no histórico.
        assert api.llm.calls[0].history == []
        assert api.llm.calls[1].history == [
            ("user", "primeira"),
            ("assistant", "eco: primeira"),
        ]


async def test_fila_da_mesma_sessao_nao_atrasa_outra_sessao():
    async with running_app(FakeLLM(delay=0.3)) as api:
        ocupada = await api.create_session()
        livre = await api.create_session()

        fila = [asyncio.create_task(api.ask(ocupada, f"p{i}")) for i in range(3)]
        await asyncio.sleep(0.05)
        start = time.perf_counter()
        response = await api.ask(livre, "oi")
        elapsed = time.perf_counter() - start
        await asyncio.gather(*fila)

        assert response.status_code == 200
        assert elapsed < 0.6  # só o tempo da própria resposta, sem a fila da outra


async def test_delete_durante_uma_pergunta_faz_a_pergunta_terminar_em_404():
    async with running_app(FakeLLM(delay=0.3)) as api:
        session_id = await api.create_session()

        pergunta = asyncio.create_task(api.ask(session_id, "oi"))
        await asyncio.sleep(0.05)  # a pergunta já está esperando o LLM
        deleted = await api.client.delete(f"/api/sessions/{session_id}")
        response = await pergunta

        assert deleted.status_code == 204
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
        assert api.app.state.store.count() == 0


async def test_timeout_total_responde_504_e_nao_grava_nada():
    async with running_app(FakeLLM(delay=2), llm_total_timeout_s=1) as api:
        session_id = await api.create_session()

        start = time.perf_counter()
        response = await api.ask(session_id, "oi")
        elapsed = time.perf_counter() - start

        assert response.status_code == 504
        assert response.json() == TIMEOUT
        assert 0.9 < elapsed < 1.8
        assert await api.history(session_id) == []


async def test_timeout_total_conta_o_tempo_na_fila_da_sessao():
    async with running_app(FakeLLM(delay=0.7), llm_total_timeout_s=1) as api:
        session_id = await api.create_session()

        first = asyncio.create_task(api.ask(session_id, "primeira"))
        await asyncio.sleep(0.05)
        second = asyncio.create_task(api.ask(session_id, "segunda"))
        responses = await asyncio.gather(first, second)

        # A segunda esperou 0,65 s na fila e não teve tempo de terminar.
        assert [r.status_code for r in responses] == [200, 504]
        assert [m["content"] for m in await api.history(session_id)] == [
            "primeira",
            "eco: primeira",
        ]


async def test_sessao_volta_a_responder_depois_de_um_timeout():
    llm = FakeLLM(delay=2)
    async with running_app(llm, llm_total_timeout_s=1) as api:
        session_id = await api.create_session()
        await api.ask(session_id, "lenta")
        llm.delay = 0

        response = await api.ask(session_id, "rápida")

        assert response.status_code == 200
        assert [m["content"] for m in await api.history(session_id)] == [
            "rápida",
            "eco: rápida",
        ]
