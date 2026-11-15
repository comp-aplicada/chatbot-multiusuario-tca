"""Aplicação FastAPI do chatbot multiusuário (PRD, seções 3 e 4.5).

Sobe com 1 worker: as sessões ficam na memória do processo (seção 4.4).

    uvicorn app.main:app --port 8000 --no-access-log
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.errors import LLMUnavailable, register_error_handlers
from app.llm.client import LLMClient
from app.openapi import use_contract_errors
from app.routes.sessions import ChatLLM, router
from app.sessions.store import SessionStore

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_S = 60


def configure_logging() -> None:
    """Logs da aplicação em INFO no terminal (são os que aparecem na demo)."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # O httpx loga uma linha por chamada ao provedor; fica só o que é nosso.
    logging.getLogger("httpx").setLevel(logging.WARNING)


class UnconfiguredLLM:
    """Usado quando LLM_API_KEY não foi definida: toda pergunta responde 503.

    Assim a API sobe sem a chave (health, sessões e Swagger funcionam) e o
    problema aparece no log, em vez de o servidor não iniciar.
    """

    async def chat(self, persona: str, history: object, question: str) -> str:
        raise LLMUnavailable()


def build_llm(settings: Settings) -> ChatLLM:
    if not settings.llm_api_key:
        logger.warning(
            "llm_api_key_missing: defina LLM_API_KEY no .env; "
            "até lá, toda pergunta responde 503"
        )
        return UnconfiguredLLM()
    return LLMClient(settings)


async def cleanup_loop(store: SessionStore, interval_s: float) -> None:
    """Remove as sessões expiradas a cada `interval_s` segundos."""
    while True:
        await asyncio.sleep(interval_s)
        try:
            removed = await store.cleanup_expired()
        except Exception:
            logger.exception("cleanup_failed")
            continue
        if removed:
            logger.info("cleanup removed=%d", removed)


def create_app(
    settings: Settings | None = None,
    *,
    cleanup_interval_s: float = CLEANUP_INTERVAL_S,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        # Instâncias únicas do processo, injetadas nas rotas com Depends.
        app.state.settings = settings
        app.state.store = SessionStore(
            ttl_min=settings.session_ttl_min, max_sessions=settings.session_max
        )
        app.state.llm = build_llm(settings)
        cleanup = asyncio.create_task(
            cleanup_loop(app.state.store, cleanup_interval_s)
        )
        try:
            yield
        finally:
            cleanup.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup

    app = FastAPI(
        title="Chatbot Multiusuário (TCA, Equipe B)",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    register_error_handlers(app)
    use_contract_errors(app)
    app.include_router(router)
    return app


app = create_app()
