"""Teste de concorrência multiusuário do chatbot (PRD, seção 8.3).

Cada usuário simulado cria uma sessão e, em paralelo com os outros, diz o
próprio nome e depois pergunta qual é. Se as sessões estiverem isoladas, cada
um recebe de volta o próprio nome e nenhum dos outros.

Uso:
    python scripts/concurrency_test.py --base-url https://<domínio> --users 10

Termina com código 1 se alguma resposta não for OK ou se houver erro HTTP.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import unicodedata
from dataclasses import dataclass

import httpx

# Nomes incomuns e distintos, para evitar acerto por acaso.
# Nenhum nome é parte de outro.
NAMES = [
    "Aurélio",
    "Benedita",
    "Cassiano",
    "Doralice",
    "Eustáquio",
    "Filomena",
    "Gumercindo",
    "Hermengarda",
    "Isidoro",
    "Jurema",
    "Leopoldina",
    "Macário",
    "Norberta",
    "Olegário",
    "Petronília",
    "Quitéria",
    "Raimunda",
    "Severino",
    "Teodolinda",
    "Ubaldo",
]

FIRST_MESSAGE = "Meu nome é {name}. Guarde isso."
SECOND_MESSAGE = "Qual é o meu nome? Responda só o nome."

OK = "OK"
FAILURE = "FALHA"
RATE_LIMIT = "RATE LIMIT"
HTTP_ERROR = "ERRO HTTP"


@dataclass
class Result:
    user: int
    expected: str
    session_id: str = ""
    reply: str = ""
    latency_s: float = 0.0
    status: str = FAILURE
    detail: str = ""


class RequestFailed(Exception):
    def __init__(self, status: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def normalize(text: str) -> str:
    """Minúsculas e sem acentos."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def is_reply_ok(reply: str, expected: str, others: list[str]) -> bool:
    """OK se contém o nome esperado e nenhum dos outros nomes do teste."""
    text = normalize(reply)
    return normalize(expected) in text and not any(
        normalize(name) in text for name in others
    )


def classify_error(response: httpx.Response) -> RequestFailed:
    try:
        error = response.json().get("error", {})
        code, message = error.get("code", ""), error.get("message", "")
    except ValueError:
        code, message = "", response.text[:80]
    if response.status_code == 503:
        return RequestFailed(RATE_LIMIT, f"rate limit do provedor (503 {code})".strip())
    return RequestFailed(HTTP_ERROR, f"{response.status_code} {code} {message}".strip())


async def request(
    client: httpx.AsyncClient, method: str, path: str, expected_status: int, **kwargs
) -> httpx.Response:
    try:
        response = await client.request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise RequestFailed(HTTP_ERROR, f"erro de rede: {type(exc).__name__}") from exc
    if response.status_code != expected_status:
        raise classify_error(response)
    return response


async def ask(client: httpx.AsyncClient, session_id: str, content: str) -> str:
    response = await request(
        client,
        "POST",
        f"/api/sessions/{session_id}/messages",
        200,
        json={"content": content},
    )
    return response.json()["reply"]["content"]


async def run_user(
    client: httpx.AsyncClient, user: int, name: str, others: list[str]
) -> Result:
    result = Result(user=user, expected=name)
    start = time.perf_counter()
    try:
        created = await request(
            client, "POST", "/api/sessions", 201, json={"persona": "geral"}
        )
        result.session_id = created.json()["session_id"]
        await ask(client, result.session_id, FIRST_MESSAGE.format(name=name))
        result.reply = await ask(client, result.session_id, SECOND_MESSAGE)
        ok = is_reply_ok(result.reply, name, others)
        result.status = OK if ok else FAILURE
        if not ok:
            result.detail = "resposta sem o nome certo ou com nome de outro usuário"
    except RequestFailed as exc:
        result.status, result.detail = exc.status, exc.detail
    finally:
        result.latency_s = time.perf_counter() - start
        if result.session_id:
            try:
                await client.delete(f"/api/sessions/{result.session_id}")
            except httpx.RequestError:
                pass
    return result


def one_line(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def print_table(results: list[Result]) -> None:
    rows = [
        (
            str(r.user),
            r.session_id[:8] or "-",
            r.expected,
            one_line(r.reply or r.detail, 48),
            f"{r.latency_s:.2f}s",
            r.status,
        )
        for r in results
    ]
    header = ("Usuário", "ID", "Nome esperado", "Resposta", "Latência", "Resultado")
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()

    print(fmt(header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


async def run(base_url: str, users: int, timeout_s: float) -> list[Result]:
    names = NAMES[:users]
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=timeout_s,
        limits=httpx.Limits(max_connections=users * 2),
    ) as client:
        tasks = [
            run_user(client, i, name, [n for n in names if n != name])
            for i, name in enumerate(names, start=1)
        ]
        return await asyncio.gather(*tasks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        required=True,
        help="URL do servidor, ex.: https://chat.exemplo.com ou http://localhost:8000",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help=f"usuários simultâneos, de 1 a {len(NAMES)} (padrão: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="timeout de cada requisição em segundos (padrão: 90)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.users <= len(NAMES):
        parser.error(f"--users deve estar entre 1 e {len(NAMES)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"{args.users} usuários simultâneos contra {args.base_url}\n")

    start = time.perf_counter()
    results = asyncio.run(run(args.base_url, args.users, args.timeout))
    elapsed = time.perf_counter() - start

    print_table(results)

    counts = {
        s: sum(r.status == s for r in results)
        for s in (OK, FAILURE, RATE_LIMIT, HTTP_ERROR)
    }
    print(
        f"\n{counts[OK]}/{len(results)} OK"
        f" | {counts[FAILURE]} falha(s) de isolamento"
        f" | {counts[RATE_LIMIT]} rate limit do provedor"
        f" | {counts[HTTP_ERROR]} erro(s) HTTP"
        f" | tempo total {elapsed:.2f}s"
    )
    return 0 if counts[OK] == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
