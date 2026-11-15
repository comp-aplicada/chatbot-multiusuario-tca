"""Rotas da API (PRD, seções 4.5 e 5).

O SessionStore e o LLMClient são instâncias únicas, criadas no lifespan do app
e injetadas com Depends. Nos testes, o LLM é trocado por um FakeLLM.
"""

import asyncio
import logging
import re
import time
from collections.abc import Sequence
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Request, Response

from app.config import Settings
from app.errors import LLMTimeout, LLMUnavailable, SessionNotFound
from app.llm.client import llm_attempts
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
from app.sessions.store import Message, SessionStore, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Erros documentados no Swagger, no formato da seção 5.6 do PRD.
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Sessão não encontrada"}}
INVALID = {422: {"model": ErrorResponse, "description": "Requisição inválida"}}
LLM_ERRORS = {
    503: {"model": ErrorResponse, "description": "Modelo indisponível"},
    504: {"model": ErrorResponse, "description": "Modelo demorou demais"},
}

_SHORT_ID = re.compile(r"[0-9a-fA-F-]{1,8}")


class ChatLLM(Protocol):
    async def chat(
        self, persona: str, history: Sequence[Message], question: str
    ) -> str: ...


def get_store(request: Request) -> SessionStore:
    return request.app.state.store


def get_llm(request: Request) -> ChatLLM:
    return request.app.state.llm


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


Store = Annotated[SessionStore, Depends(get_store)]
LLM = Annotated[ChatLLM, Depends(get_llm)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


def short(session_id: str) -> str:
    """Os 8 primeiros caracteres do ID. O ID completo nunca vai para o log.

    Um ID que não parece UUID vem do cliente e pode trazer qualquer coisa
    (inclusive quebra de linha), então não é reproduzido.
    """
    prefix = session_id[:8]
    return prefix if _SHORT_ID.fullmatch(prefix) else "invalido"


@router.get("/health", response_model=Health, tags=["health"])
async def health(store: Store, settings: AppSettings) -> Health:
    return Health(active_sessions=store.count(), model=settings.llm_model)


@router.post(
    "/sessions",
    status_code=201,
    response_model=SessionCreated,
    responses=INVALID,
    tags=["sessions"],
    summary="Conectar: cria uma sessão com ID único",
)
async def create_session(
    store: Store, body: SessionCreateRequest | None = None
) -> SessionCreated:
    session = await store.create(body.persona if body else "geral")
    logger.info("session_created sess=%s persona=%s", short(session.id), session.persona)
    return SessionCreated(
        session_id=session.id, persona=session.persona, created_at=session.created_at
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    responses=NOT_FOUND,
    tags=["sessions"],
    summary="Histórico da sessão",
)
async def get_session(session_id: str, store: Store) -> SessionDetail:
    # touch=False: ler o histórico não renova a sessão.
    session = await store.get(session_id, touch=False)
    return SessionDetail(
        session_id=session.id,
        persona=session.persona,
        created_at=session.created_at,
        last_activity=session.last_activity,
        messages=[
            MessageOut(role=m.role, content=m.content, created_at=m.created_at)
            for m in session.messages
        ],
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    responses={**NOT_FOUND, **INVALID, **LLM_ERRORS},
    tags=["sessions"],
    summary="Perguntar ao chatbot",
)
async def send_message(
    session_id: str,
    body: MessageRequest,
    store: Store,
    llm: LLM,
    settings: AppSettings,
) -> MessageResponse:
    start = time.perf_counter()
    status = 500
    try:
        # A data da pergunta é o momento em que ela foi recebida.
        user = Message(role="user", content=body.content, created_at=utcnow())
        session = await store.get(session_id, touch=True)
        try:
            # O limite vale para a requisição inteira: fila do lock da sessão,
            # tentativas do LLM e esperas entre elas.
            async with asyncio.timeout(settings.llm_total_timeout_s):
                # O lock da sessão põe em fila as perguntas da MESMA sessão.
                # Sessões diferentes não se bloqueiam.
                async with session.lock:
                    reply = await llm.chat(
                        session.persona, list(session.messages), user.content
                    )
                    assistant = Message(
                        role="assistant", content=reply, created_at=utcnow()
                    )
                    # Pergunta e resposta entram juntas. Se a sessão foi
                    # removida no meio, levanta SessionNotFound e nada é gravado.
                    await store.append_exchange(session_id, user, assistant)
        except TimeoutError:
            raise LLMTimeout() from None
        status = 200
        return MessageResponse(
            session_id=session_id,
            reply=MessageOut(
                role=assistant.role,
                content=assistant.content,
                created_at=assistant.created_at,
            ),
        )
    except SessionNotFound:
        status = 404
        raise
    except LLMUnavailable:
        status = 503
        raise
    except LLMTimeout:
        status = 504
        raise
    finally:
        logger.info(
            "message sess=%s status=%d latency_ms=%d attempts=%d",
            short(session_id),
            status,
            (time.perf_counter() - start) * 1000,
            llm_attempts.get(),
        )


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    responses=NOT_FOUND,
    tags=["sessions"],
    summary="Encerrar a sessão",
)
async def delete_session(session_id: str, store: Store) -> Response:
    await store.delete(session_id)
    logger.info("session_deleted sess=%s", short(session_id))
    return Response(status_code=204)
