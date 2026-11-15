"""SessionStore em memória (PRD, seção 4.1).

Cada sessão tem um ID único (UUID v4), um histórico isolado e um lock próprio.
As sessões ficam na memória do processo, por isso a API roda com 1 worker
(seção 4.4). A interface é pequena para poder ser trocada por Redis sem mexer
nas rotas.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from app.errors import SessionNotFound


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime  # UTC


@dataclass
class Session:
    id: str  # uuid4 em string
    persona: Literal["geral", "juridico"]
    created_at: datetime
    last_activity: datetime
    messages: list[Message] = field(default_factory=list)
    # Serializa as perguntas da MESMA sessão. Quem segura é a rota, durante
    # toda a pergunta (montar contexto, chamar o LLM, gravar).
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore:
    def __init__(
        self,
        clock: Callable[[], datetime] = utcnow,
        *,
        ttl_min: float = 30,
        max_sessions: int = 1000,
    ) -> None:
        self._clock = clock
        self._ttl = timedelta(minutes=ttl_min)
        self._max_sessions = max_sessions
        self._sessions: dict[str, Session] = {}
        # Lock global: protege só leituras e escritas no dicionário, que são
        # rápidas e não esperam a rede. Sessões diferentes não se bloqueiam.
        self._lock = asyncio.Lock()

    async def create(self, persona: str) -> Session:
        async with self._lock:
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest_idle()
            now = self._clock()
            session = Session(
                id=str(uuid4()), persona=persona, created_at=now, last_activity=now
            )
            self._sessions[session.id] = session
            return session

    async def get(self, session_id: str, touch: bool = True) -> Session:
        """Devolve a sessão. Com touch=True, renova o last_activity."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound()
            if self._is_expired(session) and not session.lock.locked():
                # Expirou e a limpeza periódica ainda não passou.
                del self._sessions[session_id]
                raise SessionNotFound()
            if touch:
                session.last_activity = self._clock()
            return session

    async def append_exchange(
        self, session_id: str, user: Message, assistant: Message
    ) -> None:
        """Grava pergunta e resposta juntas: o histórico nunca fica pela metade."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                # Removida durante a pergunta (DELETE, expiração ou limite).
                raise SessionNotFound()
            session.messages.extend((user, assistant))
            session.last_activity = self._clock()

    async def delete(self, session_id: str) -> None:
        """Remove a sessão, mesmo com o lock dela ocupado."""
        async with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFound()
            del self._sessions[session_id]

    async def cleanup_expired(self) -> int:
        """Remove as sessões expiradas e devolve quantas removeu.

        Pula as que estão com o lock ocupado, para não remover uma sessão no
        meio de uma resposta.
        """
        async with self._lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if self._is_expired(session) and not session.lock.locked()
            ]
            for session_id in expired:
                del self._sessions[session_id]
            return len(expired)

    def count(self) -> int:
        return len(self._sessions)

    def _is_expired(self, session: Session) -> bool:
        return self._clock() - session.last_activity > self._ttl

    def _evict_oldest_idle(self) -> None:
        """Remove a sessão de atividade mais antiga que não esteja ocupada.

        Se todas estiverem ocupadas, não remove nenhuma: a nova sessão é
        criada mesmo assim e o limite é excedido temporariamente.
        """
        idle = [s for s in self._sessions.values() if not s.lock.locked()]
        if idle:
            oldest = min(idle, key=lambda s: s.last_activity)
            del self._sessions[oldest.id]
