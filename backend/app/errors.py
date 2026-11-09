"""Exceções de domínio da API.

Versão mínima com as exceções do LLM, para o `LLMClient` (#8) não depender
de #6. Os handlers e o `SessionNotFound` entram em #6, mantendo estes nomes.
"""


class LLMTimeout(Exception):
    """Uma tentativa de chamada ao LLM passou de LLM_TIMEOUT_S (vira 504)."""


class LLMUnavailable(Exception):
    """O provedor falhou, recusou a chamada ou devolveu resposta vazia (vira 503)."""
