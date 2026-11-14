"""SessionStore em memória: IDs únicos, locks, TTL e limite (PRD, seção 4.1)."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.errors import SessionNotFound
from app.sessions.store import Message, Session, SessionStore

INICIO = datetime(2026, 11, 11, 14, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Relógio controlado pelo teste."""

    def __init__(self) -> None:
        self.now = INICIO

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(clock: FakeClock) -> SessionStore:
    return SessionStore(clock, ttl_min=30, max_sessions=1000)


def exchange(clock: FakeClock, question: str = "oi") -> tuple[Message, Message]:
    return (
        Message("user", question, clock()),
        Message("assistant", f"eco: {question}", clock()),
    )


# Criação e IDs


async def test_create_devolve_sessao_nova_com_uuid4(store, clock):
    session = await store.create("juridico")

    assert isinstance(session, Session)
    assert uuid.UUID(session.id).version == 4
    assert session.persona == "juridico"
    assert session.created_at == INICIO
    assert session.last_activity == INICIO
    assert session.messages == []
    assert not session.lock.locked()


async def test_cada_sessao_tem_um_id_unico(store):
    sessions = await asyncio.gather(*(store.create("geral") for _ in range(200)))

    assert len({s.id for s in sessions}) == 200
    assert store.count() == 200


async def test_cada_sessao_tem_o_proprio_historico_e_o_proprio_lock(store):
    a = await store.create("geral")
    b = await store.create("geral")

    assert a.messages is not b.messages
    assert a.lock is not b.lock


# get


async def test_get_devolve_a_sessao_criada(store):
    created = await store.create("geral")

    assert await store.get(created.id) is created


@pytest.mark.parametrize("session_id", [str(uuid.uuid4()), "nao-e-um-uuid", ""])
async def test_get_de_id_inexistente_levanta_session_not_found(store, session_id):
    with pytest.raises(SessionNotFound):
        await store.get(session_id)


async def test_get_renova_last_activity(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=5)

    await store.get(session.id)

    assert session.last_activity == INICIO + timedelta(minutes=5)
    assert session.created_at == INICIO


async def test_get_com_touch_false_nao_renova_last_activity(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=5)

    await store.get(session.id, touch=False)

    assert session.last_activity == INICIO


# append_exchange


async def test_append_exchange_grava_pergunta_e_resposta_juntas(store, clock):
    session = await store.create("geral")
    user, assistant = exchange(clock, "Qual é a capital do Piauí?")

    await store.append_exchange(session.id, user, assistant)

    assert session.messages == [user, assistant]


async def test_append_exchange_renova_last_activity(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=10)

    await store.append_exchange(session.id, *exchange(clock))

    assert session.last_activity == INICIO + timedelta(minutes=10)


async def test_append_exchange_mantem_a_ordem_das_trocas(store, clock):
    session = await store.create("geral")

    await store.append_exchange(session.id, *exchange(clock, "primeira"))
    await store.append_exchange(session.id, *exchange(clock, "segunda"))

    assert [m.content for m in session.messages] == [
        "primeira",
        "eco: primeira",
        "segunda",
        "eco: segunda",
    ]


async def test_append_exchange_em_sessao_removida_levanta_e_nao_grava(store, clock):
    session = await store.create("geral")
    await store.delete(session.id)

    with pytest.raises(SessionNotFound):
        await store.append_exchange(session.id, *exchange(clock))

    assert session.messages == []


async def test_historicos_de_sessoes_diferentes_nao_se_misturam(store, clock):
    a = await store.create("geral")
    b = await store.create("geral")

    await store.append_exchange(a.id, *exchange(clock, "pergunta de A"))
    await store.append_exchange(b.id, *exchange(clock, "pergunta de B"))

    assert [m.content for m in a.messages] == ["pergunta de A", "eco: pergunta de A"]
    assert [m.content for m in b.messages] == ["pergunta de B", "eco: pergunta de B"]


# delete e count


async def test_delete_remove_a_sessao(store):
    session = await store.create("geral")

    await store.delete(session.id)

    assert store.count() == 0
    with pytest.raises(SessionNotFound):
        await store.get(session.id)


async def test_delete_de_id_inexistente_levanta_session_not_found(store):
    with pytest.raises(SessionNotFound):
        await store.delete(str(uuid.uuid4()))


async def test_delete_remove_mesmo_com_o_lock_ocupado(store):
    session = await store.create("geral")

    async with session.lock:
        await store.delete(session.id)

    assert store.count() == 0


async def test_count_acompanha_criacoes_e_remocoes(store):
    assert store.count() == 0
    a = await store.create("geral")
    await store.create("geral")
    assert store.count() == 2
    await store.delete(a.id)
    assert store.count() == 1


# Expiração (TTL)


async def test_cleanup_remove_sessao_inativa_ha_mais_que_o_ttl(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=30, seconds=1)

    removed = await store.cleanup_expired()

    assert removed == 1
    assert store.count() == 0
    with pytest.raises(SessionNotFound):
        await store.get(session.id)


async def test_cleanup_nao_remove_sessao_exatamente_no_ttl(store, clock):
    await store.create("geral")
    clock.advance(minutes=30)

    assert await store.cleanup_expired() == 0
    assert store.count() == 1


async def test_cleanup_so_remove_as_expiradas(store, clock):
    velha = await store.create("geral")
    clock.advance(minutes=20)
    nova = await store.create("geral")
    clock.advance(minutes=15)

    assert await store.cleanup_expired() == 1

    assert await store.get(nova.id) is nova
    with pytest.raises(SessionNotFound):
        await store.get(velha.id)


async def test_atividade_adia_a_expiracao(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=20)
    await store.get(session.id)
    clock.advance(minutes=20)

    assert await store.cleanup_expired() == 0
    assert store.count() == 1


async def test_leitura_do_historico_nao_adia_a_expiracao(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=20)
    await store.get(session.id, touch=False)
    clock.advance(minutes=20)

    assert await store.cleanup_expired() == 1


async def test_cleanup_pula_sessao_com_lock_ocupado(store, clock):
    ocupada = await store.create("geral")
    livre = await store.create("geral")
    clock.advance(minutes=31)

    async with ocupada.lock:
        removed = await store.cleanup_expired()

        assert removed == 1
        assert store.count() == 1
        assert await store.get(ocupada.id, touch=False) is ocupada
        with pytest.raises(SessionNotFound):
            await store.get(livre.id)


async def test_get_de_sessao_expirada_ainda_nao_limpa_levanta_session_not_found(
    store, clock
):
    session = await store.create("geral")
    clock.advance(minutes=31)

    with pytest.raises(SessionNotFound):
        await store.get(session.id)

    assert store.count() == 0


async def test_get_de_sessao_expirada_com_lock_ocupado_devolve_a_sessao(store, clock):
    session = await store.create("geral")
    clock.advance(minutes=31)

    async with session.lock:
        assert await store.get(session.id, touch=False) is session


async def test_ttl_vem_do_construtor(clock):
    store = SessionStore(clock, ttl_min=1, max_sessions=10)
    await store.create("geral")
    clock.advance(seconds=61)

    assert await store.cleanup_expired() == 1


# Limite de sessões


async def test_ao_passar_do_limite_remove_a_de_atividade_mais_antiga(clock):
    store = SessionStore(clock, ttl_min=30, max_sessions=3)
    primeira = await store.create("geral")
    clock.advance(seconds=1)
    segunda = await store.create("geral")
    clock.advance(seconds=1)
    terceira = await store.create("geral")
    clock.advance(seconds=1)
    await store.get(primeira.id)  # a primeira passa a ser a mais recente
    clock.advance(seconds=1)

    quarta = await store.create("geral")

    assert store.count() == 3
    with pytest.raises(SessionNotFound):
        await store.get(segunda.id)
    for session in (primeira, terceira, quarta):
        assert await store.get(session.id) is session


async def test_limite_nao_remove_sessao_com_lock_ocupado(clock):
    store = SessionStore(clock, ttl_min=30, max_sessions=2)
    mais_antiga = await store.create("geral")
    clock.advance(seconds=1)
    segunda = await store.create("geral")
    clock.advance(seconds=1)

    async with mais_antiga.lock:
        await store.create("geral")

    assert store.count() == 2
    assert await store.get(mais_antiga.id) is mais_antiga
    with pytest.raises(SessionNotFound):
        await store.get(segunda.id)


async def test_com_todas_ocupadas_cria_mesmo_assim_e_excede_o_limite(clock):
    store = SessionStore(clock, ttl_min=30, max_sessions=2)
    a = await store.create("geral")
    b = await store.create("geral")

    async with a.lock, b.lock:
        nova = await store.create("geral")

    assert store.count() == 3
    assert await store.get(nova.id) is nova


async def test_abaixo_do_limite_nao_remove_ninguem(clock):
    store = SessionStore(clock, ttl_min=30, max_sessions=3)
    sessions = [await store.create("geral") for _ in range(3)]

    assert store.count() == 3
    for session in sessions:
        assert await store.get(session.id) is session


# Relógio


async def test_relogio_padrao_e_utc():
    store = SessionStore()

    session = await store.create("geral")

    assert session.created_at.tzinfo == timezone.utc
    assert abs(datetime.now(timezone.utc) - session.created_at) < timedelta(seconds=5)
