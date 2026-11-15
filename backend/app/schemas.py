"""Modelos Pydantic do contrato da API (PRD, seção 5)."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer, StringConstraints, WithJsonSchema

from app.config import get_settings

Persona = Literal["geral", "juridico"]
Role = Literal["user", "assistant"]


def to_iso_utc(value: datetime) -> str:
    """ISO 8601 em UTC com Z e sem fração, ex.: 2026-11-11T14:00:00Z."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(to_iso_utc, return_type=str),
    WithJsonSchema(
        {"type": "string", "format": "date-time", "examples": ["2026-11-11T14:00:00Z"]},
        mode="serialization",
    ),
]

# De 1 a MESSAGE_MAX_CHARS caracteres, contados depois do strip().
MessageContent = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=get_settings().message_max_chars,
    ),
]


class SessionCreateRequest(BaseModel):
    persona: Persona = "geral"


class SessionCreated(BaseModel):
    session_id: str
    persona: Persona
    created_at: UtcDatetime


class MessageOut(BaseModel):
    role: Role
    content: str
    created_at: UtcDatetime


class SessionDetail(BaseModel):
    session_id: str
    persona: Persona
    created_at: UtcDatetime
    last_activity: UtcDatetime
    messages: list[MessageOut]


class MessageRequest(BaseModel):
    content: MessageContent


class MessageResponse(BaseModel):
    session_id: str
    reply: MessageOut


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    active_sessions: int
    model: str


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
