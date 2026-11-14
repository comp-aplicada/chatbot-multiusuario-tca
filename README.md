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
- [Achados e aprendizados](docs/achados.md): problemas e descobertas do desenvolvimento, para estudar para a apresentação

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
