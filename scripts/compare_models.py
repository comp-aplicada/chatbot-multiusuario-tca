"""Compara modelos do LLM com 10 perguntas fixas (seção 8.5 do PRD).

Usa os prompts reais de backend/app/llm/personas.py e só a biblioteca padrão.
Cada modelo roda as perguntas em sequência, e os modelos rodam em paralelo.

Uso:
    DEEPINFRA_API_KEY=... GROQ_API_KEY=... python scripts/compare_models.py \
        --out docs/escolha-do-modelo-dados.json

O resultado bruto (respostas, latências e tokens) vai para o JSON; a tabela e
a conclusão ficam em docs/escolha-do-modelo.md.
"""

import argparse
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROVIDERS = {
    "deepinfra": {
        "base_url": "https://api.deepinfra.com/v1/openai",
        "key_env": "DEEPINFRA_API_KEY",
        "extra_body": {},
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "extra_body": {"reasoning_effort": "none"},
    },
}

# Parâmetros extras por modelo, além dos do provedor. O Qwen3.8 ignora o
# /no_think e raciocina escondido, gastando o max_tokens, sem isto.
MODEL_EXTRA_BODY = {
    "Qwen/Qwen3.8-27B": {"reasoning_effort": "none"},
}

MODELS = [
    ("deepinfra", "Qwen/Qwen3-32B"),
    ("deepinfra", "Qwen/Qwen3-14B"),
    ("deepinfra", "Qwen/Qwen3-30B-A3B"),
    ("deepinfra", "Qwen/Qwen3-235B-A22B-Instruct-2507"),
    ("deepinfra", "Qwen/Qwen3.8-27B"),
    ("groq", "qwen/qwen3.8-27b"),
]

# (id, categoria, persona, turnos). Só o último turno é medido; os anteriores
# montam o histórico, como na API do chatbot.
QUESTIONS = [
    ("q1", "conhecimento geral", "geral", ["Qual é a capital da Austrália?"]),
    ("q2", "conhecimento geral", "geral",
     ["Quem escreveu Dom Casmurro e em que ano o livro foi publicado?"]),
    ("q3", "conhecimento geral", "geral", ["Por que o céu é azul? Responda em poucas linhas."]),
    ("q4", "explicação técnica", "geral", ["Explique em poucas linhas o que é uma API REST."]),
    ("q5", "explicação técnica", "geral", ["Qual é a diferença entre processo e thread?"]),
    ("q6", "raciocínio simples", "geral",
     ["Se tenho 3 caixas com 4 maçãs cada e como 5, quantas sobram?"]),
    ("q7", "raciocínio simples", "geral",
     ["Um ônibus sai às 14h40 e a viagem dura 2h35. A que horas ele chega?"]),
    ("q8", "jurídica", "juridico",
     ["Comprei um produto pela internet e me arrependi. Posso devolver?"]),
    ("q9", "jurídica", "juridico", ["Fui demitido sem justa causa. Quais verbas eu recebo?"]),
    ("q10", "continuidade de contexto", "geral",
     ["Meu nome é Epaminondas e eu moro em Teresina. Guarde isso.",
      "Qual é o meu nome e em que cidade eu moro?"]),
]


def load_personas() -> dict[str, str]:
    path = ROOT / "backend" / "app" / "llm" / "personas.py"
    spec = importlib.util.spec_from_file_location("personas", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PERSONAS


def call(provider: str, model: str, messages: list[dict], max_tokens: int) -> dict:
    cfg = PROVIDERS[provider]
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        **cfg["extra_body"],
        **MODEL_EXTRA_BODY.get(model, {}),
    }).encode()
    headers = {
        "Authorization": f"Bearer {os.environ[cfg['key_env']]}",
        "Content-Type": "application/json",
        "User-Agent": "compare-models",
    }
    for _ in range(10):
        req = urllib.request.Request(f"{cfg['base_url']}/chat/completions", body, headers)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            # O Groq gratuito limita tokens de saída por minuto; espera e tenta de novo.
            if exc.code == 429:
                time.sleep(float(exc.headers.get("retry-after") or 10) + 1)
                continue
            raise
        latency = time.perf_counter() - start
        choice = data["choices"][0]
        return {
            "content": choice["message"]["content"] or "",
            "finish_reason": choice.get("finish_reason"),
            "latency_s": round(latency, 2),
            "completion_tokens": data["usage"]["completion_tokens"],
            "cost_usd": data["usage"].get("estimated_cost"),
        }
    raise RuntimeError("429 repetido")


def run_model(provider: str, model: str, personas: dict[str, str], max_tokens: int) -> dict:
    results = []
    for qid, category, persona, turns in QUESTIONS:
        messages = [{"role": "system", "content": personas[persona]}]
        for turn in turns[:-1]:
            messages.append({"role": "user", "content": turn})
            prev = call(provider, model, messages, max_tokens)
            messages.append({"role": "assistant", "content": prev["content"]})
        messages.append({"role": "user", "content": turns[-1]})
        result = call(provider, model, messages, max_tokens)
        results.append({"id": qid, "categoria": category, "persona": persona,
                        "pergunta": turns[-1], **result})
        print(f"{model:40} {qid:4} {result['latency_s']:6.1f}s", flush=True)
    return {"provider": provider, "model": model, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="docs/escolha-do-modelo-dados.json")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--models", nargs="*", help="roda só estes modelos e junta ao --out")
    args = parser.parse_args()

    personas = load_personas()
    models = [m for m in MODELS if os.environ.get(PROVIDERS[m[0]]["key_env"])]
    if args.models:
        models = [m for m in models if m[1] in args.models]
    if not models:
        keys = " ou ".join(p["key_env"] for p in PROVIDERS.values())
        parser.error(f"nenhum modelo para rodar: defina {keys} (e confira o --models)")
    with ThreadPoolExecutor(len(models)) as pool:
        runs = list(pool.map(lambda m: run_model(*m, personas, args.max_tokens), models))

    out = Path(args.out)
    if args.models and out.exists():
        new = {r["model"] for r in runs}
        old = [r for r in json.loads(out.read_text())["runs"] if r["model"] not in new]
        order = [m for _, m in MODELS]
        runs = sorted(old + runs, key=lambda r: order.index(r["model"]))

    out.write_text(json.dumps(
        {"data": time.strftime("%Y-%m-%d"), "max_tokens": args.max_tokens,
         "personas": personas, "runs": runs},
        ensure_ascii=False, indent=2) + "\n")
    print(f"\nResultados em {args.out}")


if __name__ == "__main__":
    main()
