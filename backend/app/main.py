"""Stub da API do chatbot: as 5 rotas do contrato (PRD, seção 5) com respostas fixas.

Serve para o front, a infra e os scripts programarem contra o formato real
antes de a lógica existir. As sessões reais (#7) e o LLM (#8) entram depois.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Response

from app.config import get_settings
from app.errors import SessionNotFound, register_error_handlers
from app.openapi import use_contract_errors
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

app = FastAPI(
    title="Chatbot Multiusuário (TCA, Equipe B)",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
register_error_handlers(app)
use_contract_errors(app)

# Erros documentados no Swagger, no formato da seção 5.6 do PRD.
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Sessão não encontrada"}}
INVALID = {422: {"model": ErrorResponse, "description": "Requisição inválida"}}
LLM_ERRORS = {
    503: {"model": ErrorResponse, "description": "Modelo indisponível"},
    504: {"model": ErrorResponse, "description": "Modelo demorou demais"},
}

# Sessões criadas. Basta para o 404 funcionar.
sessions: dict[str, SessionCreated] = {}


def now() -> datetime:
    return datetime.now(timezone.utc)


def find(session_id: str) -> SessionCreated:
    try:
        return sessions[session_id]
    except KeyError:
        raise SessionNotFound() from None


@app.get("/api/health", response_model=Health, tags=["health"])
async def health() -> Health:
    return Health(active_sessions=len(sessions), model=get_settings().llm_model)


@app.post(
    "/api/sessions",
    status_code=201,
    response_model=SessionCreated,
    responses=INVALID,
    tags=["sessions"],
    summary="Conectar: cria uma sessão com ID único",
)
async def create_session(body: SessionCreateRequest | None = None) -> SessionCreated:
    session = SessionCreated(
        session_id=str(uuid4()),
        persona=body.persona if body else "geral",
        created_at=now(),
    )
    sessions[session.session_id] = session
    return session


@app.get(
    "/api/sessions/{session_id}",
    response_model=SessionDetail,
    responses=NOT_FOUND,
    tags=["sessions"],
    summary="Histórico da sessão",
)
async def get_session(session_id: str) -> SessionDetail:
    session = find(session_id)
    return SessionDetail(
        session_id=session_id,
        persona=session.persona,
        created_at=session.created_at,
        last_activity=now(),
        messages=[
            MessageOut(
                role="user",
                content="O que é computação em nuvem?",
                created_at=session.created_at,
            ),
            MessageOut(
                role="assistant",
                content="Computação em nuvem é o uso de servidores pela internet.",
                created_at=session.created_at,
            ),
        ],
    )


@app.post(
    "/api/sessions/{session_id}/messages",
    response_model=MessageResponse,
    responses={**NOT_FOUND, **INVALID, **LLM_ERRORS},
    tags=["sessions"],
    summary="Perguntar ao chatbot",
)
async def send_message(session_id: str, body: MessageRequest) -> MessageResponse:
    find(session_id)
    return MessageResponse(
        session_id=session_id,
        reply=MessageOut(
            role="assistant", content=f"eco: {body.content}", created_at=now()
        ),
    )


@app.delete(
    "/api/sessions/{session_id}",
    status_code=204,
    responses=NOT_FOUND,
    tags=["sessions"],
    summary="Encerrar a sessão",
)
async def delete_session(session_id: str) -> Response:
    find(session_id)
    del sessions[session_id]
    return Response(status_code=204)
