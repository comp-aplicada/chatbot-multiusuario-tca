"""Exceções de domínio e formato único de erro da API (PRD, seção 5.6).

Todo erro sai como {"error": {"code": ..., "message": ...}}. O front mostra a
`message` direto para o usuário, então os textos são os da tabela 5.6.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class SessionNotFound(Exception):
    """ID inexistente, expirado ou removido (vira 404)."""


class LLMTimeout(Exception):
    """Uma tentativa passou de LLM_TIMEOUT_S, ou a requisição inteira passou de
    LLM_TOTAL_TIMEOUT_S (vira 504)."""


class LLMUnavailable(Exception):
    """O provedor falhou, recusou a chamada ou devolveu resposta vazia (vira 503)."""


# exceção -> (status HTTP, code, message)
DOMAIN_ERRORS: dict[type[Exception], tuple[int, str, str]] = {
    SessionNotFound: (404, "session_not_found", "Sessão não encontrada ou expirada."),
    LLMUnavailable: (
        503,
        "llm_unavailable",
        "O modelo está indisponível no momento. Tente novamente.",
    ),
    LLMTimeout: (
        504,
        "llm_timeout",
        "O modelo demorou demais para responder. Tente novamente.",
    ),
}


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def describe_validation_error(error: dict[str, Any]) -> str:
    """Detalhe do campo, em português, para a mensagem do 422."""
    kind = error["type"]
    if kind == "json_invalid":
        return "o corpo não é um JSON válido"

    loc = list(error.get("loc", ()))
    if loc and loc[0] == "body":
        loc = loc[1:]
    field = ".".join(str(part) for part in loc)
    ctx = error.get("ctx") or {}

    if not field:
        if kind == "missing":
            return "o corpo da requisição é obrigatório"
        return error["msg"]
    if kind == "missing":
        return f"{field} é obrigatório"
    if kind == "string_too_short":
        return f"{field} não pode ficar vazio"
    if kind == "string_too_long":
        return f"{field} deve ter no máximo {ctx['max_length']} caracteres"
    if kind == "string_type":
        return f"{field} deve ser um texto"
    if kind == "literal_error":
        return f"{field} deve ser {ctx['expected'].replace(' or ', ' ou ')}"
    return f"{field}: {error['msg']}"


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    return error_response(*DOMAIN_ERRORS[type(exc)])


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    detail = describe_validation_error(exc.errors()[0]).rstrip(".")
    return error_response(422, "invalid_request", f"Requisição inválida: {detail}.")


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Loga o modelo da rota, nunca o caminho real: o ID da sessão não vai para o log.
    route = getattr(request.scope.get("route"), "path", "?")
    logger.error(
        "internal_error method=%s route=%s", request.method, route, exc_info=exc
    )
    return error_response(500, "internal_error", "Erro interno do servidor.")


def register_error_handlers(app: FastAPI) -> None:
    for exc_class in DOMAIN_ERRORS:
        app.add_exception_handler(exc_class, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
