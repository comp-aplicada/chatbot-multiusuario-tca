"""Stub da API do chatbot: as 5 rotas do contrato (PRD, seção 5) com respostas fixas.

Serve para o front, a infra e os scripts programarem contra o formato real
antes de a lógica existir. As sessões reais (#7) e o LLM (#8) entram depois.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

MODEL = "qwen/qwen3.8-27b"

Persona = Literal["geral", "juridico"]


class SessionCreateRequest(BaseModel):
    persona: Persona = "geral"


class MessageRequest(BaseModel):
    content: str


class SessionNotFound(Exception):
    pass


app = FastAPI(
    title="Chatbot Multiusuário (TCA, Equipe B)",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

# IDs criados, com a persona e a data de criação. Basta para o 404 funcionar.
sessions: dict[str, dict[str, str]] = {}


def now_iso() -> str:
    """Data atual em ISO 8601 UTC com Z, ex.: 2026-11-11T14:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find(session_id: str) -> dict[str, str]:
    try:
        return sessions[session_id]
    except KeyError:
        raise SessionNotFound() from None


@app.exception_handler(SessionNotFound)
async def session_not_found(request, exc) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "session_not_found",
                "message": "Sessão não encontrada ou expirada.",
            }
        },
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "active_sessions": len(sessions), "model": MODEL}


@app.post("/api/sessions", status_code=201)
async def create_session(body: SessionCreateRequest | None = None) -> dict:
    session_id = str(uuid4())
    persona = body.persona if body else "geral"
    sessions[session_id] = {"persona": persona, "created_at": now_iso()}
    return {"session_id": session_id, **sessions[session_id]}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    session = find(session_id)
    return {
        "session_id": session_id,
        "persona": session["persona"],
        "created_at": session["created_at"],
        "last_activity": now_iso(),
        "messages": [
            {
                "role": "user",
                "content": "O que é computação em nuvem?",
                "created_at": session["created_at"],
            },
            {
                "role": "assistant",
                "content": "Computação em nuvem é o uso de servidores pela internet.",
                "created_at": session["created_at"],
            },
        ],
    }


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest) -> dict:
    find(session_id)
    return {
        "session_id": session_id,
        "reply": {
            "role": "assistant",
            "content": f"eco: {body.content}",
            "created_at": now_iso(),
        },
    }


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    find(session_id)
    del sessions[session_id]
    return Response(status_code=204)
