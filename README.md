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
| Demo (24/11 em diante) | DeepInfra (pago) | `https://api.deepinfra.com/v1/openai` | `Qwen/Qwen3-32B` | `{}` |

O Groq desligou o `qwen/qwen3-32b` em 17/07/2026 ([deprecações](https://console.groq.com/docs/deprecations)). No Groq, o único Qwen disponível hoje é o `qwen/qwen3.8-27b`, ainda em *preview*. Na DeepInfra, o `Qwen/Qwen3-32B` continua disponível. Trocar de provedor é só mudar essas três variáveis no `.env` (modelo em `.env.example`).

### Limites do Groq para o `qwen/qwen3.8-27b`

| Requisições por minuto | Requisições por dia | Tokens por minuto | Tokens por dia |
|---|---|---|---|
| 30 | 1.000 | 8.000 | 200.000 |

Fonte: [Rate Limits do Groq](https://console.groq.com/docs/rate-limits), consultada em 09/11/2026. A página não deixa claro se a tabela é do plano gratuito ou do Developer; confira em **Settings > Limits** no painel do Groq com a chave da equipe.

### Decisão do teste de concorrência

O teste de concorrência (`scripts/concurrency_test.py`) faz 2 mensagens por usuário. Com 10 usuários são 20 requisições em poucos segundos, o que cabe nas 30 requisições por minuto. O limite apertado é o de tokens: cada requisição usa cerca de 150 tokens de entrada (system prompt + histórico curto) e, se o Groq reservar o `max_tokens` (1024) na conta do limite, 20 requisições passam de 8.000 tokens por minuto.

Por isso:

- **No Groq:** `--users 5`.
- **Na DeepInfra (demo):** `--users 10`.
