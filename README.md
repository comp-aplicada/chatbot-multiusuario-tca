# Chatbot Multiusuário (TCA, Equipe B)

Chatbot multiusuário com LLM da Equipe B para a 2ª avaliação (apresentação em 26/11/2026).

## Estrutura

| Pasta | Conteúdo | Dono |
|---|---|---|
| `backend/` | API FastAPI, sessões e cliente do LLM | Maria Eduarda e Eduardo |
| `frontend/` | Interface de chat em React + Vite | Izaías |
| `infra/` | Nginx, Dockerfile do front e deploy na EC2 | Pedro |
| `scripts/` | Teste de concorrência e smoke test | Eduardo e Pedro |
| `docs/` | Enunciado, PRD e planos | Todos |

## Backend: como rodar e testar

A API fica em `backend/` e precisa do **Python 3.12**. Os comandos abaixo partem da raiz do repositório.

### 1. Ambiente virtual e dependências

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

No Windows, a ativação é `.venv\Scripts\activate`. O `requirements-dev.txt` instala as dependências da API e as de teste; em produção basta o `requirements.txt`.

### 2. Configuração

O `.env` fica na **raiz do repositório** (é o mesmo arquivo que o Docker Compose usa) e nunca é versionado:

```bash
cp ../.env.example ../.env
```

Abra o `.env` e preencha `LLM_API_KEY` com a chave do provedor. As outras variáveis já vêm com os valores padrão da seção 7.1 do [PRD](docs/prd-chatbot-multiusuario.md).

Sem a chave, a API sobe mesmo assim: o health, as sessões e o Swagger funcionam, o log avisa `llm_api_key_missing` e toda pergunta responde 503 `llm_unavailable`.

### 3. Subir a API

```bash
uvicorn app.main:app --reload --port 8000 --no-access-log
```

- Swagger: <http://localhost:8000/api/docs>
- Teste rápido: `curl http://localhost:8000/api/health` responde `{"status":"ok","active_sessions":0,"model":"..."}`

O `--no-access-log` desliga o log de acesso do Uvicorn, que mostraria o ID completo de cada sessão na URL. O ID funciona como um token, então os logs da aplicação mostram só os 8 primeiros caracteres:

```
2026-11-26 14:00:00,120 INFO app.routes.sessions: session_created sess=3f2a9c1e persona=geral
2026-11-26 14:00:07,954 INFO app.routes.sessions: message sess=3f2a9c1e status=200 latency_ms=1834 attempts=1
2026-11-26 14:05:12,301 INFO app.routes.sessions: session_deleted sess=3f2a9c1e
2026-11-26 14:36:00,008 INFO app.main: cleanup removed=2
```

### 4. Rodar os testes

```bash
pytest
```

Os testes não usam a rede nem a chave: o provedor do LLM é simulado. Para ver o nome de cada caso, use `pytest -v`.

| Arquivo | O que cobre |
|---|---|
| `tests/test_session_store.py` | IDs únicos, expiração por inatividade, limite de sessões e locks |
| `tests/test_rotas.py` | Todos os códigos de sucesso e erro do contrato, formato de erro, logs e Swagger |
| `tests/test_concorrencia.py` | 10 sessões em paralelo, ordem na mesma sessão, `DELETE` durante uma pergunta e timeout total |
| `tests/test_config.py`, `test_schemas.py`, `test_errors.py` | Leitura do `.env`, modelos do contrato e mensagens de erro |
| `tests/test_llm_client.py`, `test_personas.py` | Cliente do LLM (retry, timeout, limpeza do `<think>`) e prompts |

O teste que prova o requisito multiusuário é o de concorrência:

```bash
pytest tests/test_concorrencia.py -v
```

Com um LLM falso que demora 1 s, 10 sessões perguntam ao mesmo tempo e terminam em cerca de 1 s no total (em série seriam 10 s), cada uma com a resposta da própria pergunta.

### Sessões, locks, TTL e por que 1 worker

Cada conexão recebe um UUID v4 e um histórico só dela, guardados na memória do processo. Há dois níveis de lock: um lock global, segurado só durante leituras e escritas no dicionário de sessões (operações rápidas, sem esperar a rede), e um lock por sessão, segurado durante toda a pergunta. Assim, duas perguntas simultâneas na mesma sessão ficam em fila e o histórico mantém a ordem, enquanto sessões diferentes nunca se bloqueiam: enquanto uma espera o LLM, o asyncio atende as outras. Pergunta e resposta são gravadas juntas, então uma falha do LLM não deixa pergunta sem resposta no histórico. Uma sessão expira depois de `SESSION_TTL_MIN` minutos sem atividade (30 por padrão), e uma tarefa de fundo remove as expiradas a cada 60 s, pulando as que estão no meio de uma resposta; ao passar de `SESSION_MAX`, a de atividade mais antiga é removida. Como as sessões vivem na memória de um processo, o Uvicorn roda com **1 worker**: com mais de um, cada processo teria o próprio dicionário e o usuário cairia em um worker que não conhece a sessão dele. A concorrência vem do asyncio, não de vários processos. Para escalar horizontalmente, basta trocar o `SessionStore` por uma implementação com Redis, sem mexer nas rotas.

## Documentos

- [Enunciado do trabalho](docs/tarefa.md)
- [PRD / spec técnica](docs/prd-chatbot-multiusuario.md)
- [Plano do front-end](docs/plano-frontend.md)
- [Regras para agentes e commits](AGENTS.md)

## Modelo LLM

### Provedores e IDs

| Fase | Provedor | `LLM_BASE_URL` | `LLM_MODEL` | `LLM_EXTRA_BODY` |
|---|---|---|---|---|
| Desenvolvimento | Groq (gratuito) | `https://api.groq.com/openai/v1` | `qwen/qwen3.8-27b` | `{"reasoning_effort":"none"}` |
| Demo (24/11 em diante) | DeepInfra (pago) | `https://api.deepinfra.com/v1/openai` | `Qwen/Qwen3.8-27B` | `{"reasoning_effort":"none"}` |

O Groq desligou o `qwen/qwen3-32b` em 17/07/2026 ([deprecações](https://console.groq.com/docs/deprecations)). No Groq, o único Qwen disponível hoje é o `qwen/qwen3.8-27b`, ainda em *preview*. A demo usa o mesmo modelo na DeepInfra (`Qwen/Qwen3.8-27B`), que na comparação de 14/11 foi mais rápido e mais correto que o `Qwen/Qwen3-32B` ([escolha do modelo](docs/escolha-do-modelo.md)). Nos dois provedores o `LLM_EXTRA_BODY` leva `reasoning_effort: none`. Na DeepInfra ele é obrigatório: sem ele, o modelo ignora o `/no_think`, raciocina escondido, gasta o `max_tokens` e devolve a resposta cortada. Trocar de provedor é só mudar essas três variáveis no `.env` (modelo em `.env.example`).

### Limites do Groq para o `qwen/qwen3.8-27b`

| Requisições por minuto | Requisições por dia | Tokens por minuto | Tokens por dia |
|---|---|---|---|
| 30 | 1.000 | 8.000 | 200.000 |

Conferido em **Settings > Limits** no painel do Groq com a chave da equipe em 14/11/2026 (plano gratuito). Os valores batem com a página de [Rate Limits do Groq](https://console.groq.com/docs/rate-limits).

Há também um limite de **1.000 tokens de saída por minuto** que não aparece no painel. Cada chamada reserva de 440 a 512 tokens dele antes de responder, então duas ou três respostas longas seguidas dão 429, e o Groq pede de 8 a 12 s de espera. No desenvolvimento isso pode aparecer como 503 de vez em quando; na demo, com a DeepInfra, não acontece.

### Decisão do teste de concorrência

O teste de concorrência (`scripts/concurrency_test.py`) faz 2 mensagens por usuário. As requisições cabem com folga nas 30 por minuto; o limite apertado é o de tokens por minuto. O Groq desconta do limite uma estimativa feita na hora da chamada, que cresce com o `max_tokens`: com `max_tokens=1024`, uma chamada de 30 tokens reais consumiu cerca de 360 do limite.

Medição em 14/11/2026, chamando o Groq direto com a persona `geral`, `max_tokens=1024` e os mesmos dois passos do script (nome e pergunta do nome), todos os usuários em paralelo:

| Usuários | Requisições | Respostas certas | 429 | Menor saldo de tokens no minuto |
|---|---|---|---|---|
| 10 | 20 | 19 | 1 (limite de tokens de saída) | ~5.200 |
| 5 | 10 | 10 | 0 | ~5.200 |

Com 10 usuários, uma chamada bateu no limite. O `LLMClient` tentaria de novo depois de 1 s e provavelmente passaria, mas a demo não deve depender disso.

Por isso:

- **No Groq:** `--users 5`.
- **Na DeepInfra (demo):** `--users 10`.
