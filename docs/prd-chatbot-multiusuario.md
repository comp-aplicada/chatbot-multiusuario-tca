# Spec: Chatbot Multiusuário com LLM (Equipe B, TCA)

- **Data:** 04/11/2026
- **Apresentação:** 11/11/2026, presencial, 30 minutos
- **Equipe B:** Pedro Feitosa Soares, Izaías de Melo Lima Morais, Maria Eduarda Farias Gomes, Eduardo Melo de Carvalho
- **Status:** aprovada em brainstorming, aguardando revisão

---

## 1. Contexto e objetivo

O trabalho pede um chatbot simplificado em que **vários usuários se conectam ao mesmo servidor ao mesmo tempo**, cada um com um **ID de sessão único gerado na conexão**, **histórico isolado** e respostas de um LLM entregues **ao usuário certo**. A aplicação deve ser pública na internet, documentada e publicada no GitHub. A implantação em **AWS EC2** vale **+1,0 ponto** e será feita.

### 1.1 Objetivos (o que precisa funcionar em 11/11)

1. Criar sessão com ID único (UUID v4) no momento da conexão do cliente HTTP.
2. Enviar perguntas e receber respostas de um LLM (Qwen3) com o contexto da conversa daquela sessão.
3. Manter o histórico isolado por sessão, com várias sessões funcionando em paralelo.
4. Front-end web de chat acessível por HTTPS em domínio público.
5. API documentada (Swagger automático + README com exemplos `curl`).
6. Deploy em EC2 com Docker Compose.
7. Contribuição individual clara e equilibrada dos 4 integrantes (o professor avalia individualmente).

### 1.2 Fora do escopo (não fazer)

- Login, cadastro ou autenticação de usuários (a sessão anônima por UUID basta).
- Persistência em banco (o histórico se perde se o servidor reiniciar, e isso é aceitável).
- Streaming de resposta (SSE ou WebSocket).
- CI/CD com deploy automático.
- Mais de um processo/worker da API (ver 4.4).
- Upload de arquivos, RAG ou ferramentas (tool calling).

---

## 2. Decisões técnicas e justificativas

O enunciado exige justificativa técnica da escolha de modelo e framework. Estes são os argumentos para a apresentação:

| Decisão | Escolha | Justificativa | Alternativas descartadas |
|---|---|---|---|
| Tema | **Assistente genérico + persona opcional** ("geral" ou "juridico") | Cumpre "perguntas genéricas" e a persona dá um diferencial sem fugir do requisito; trocar a persona só troca o *system prompt* | Puramente jurídico (risco de fugir do enunciado) |
| Backend | **Python 3.12 + FastAPI + Uvicorn** | Assíncrono nativo (asyncio): enquanto uma requisição espera o LLM (I/O), o servidor atende outras, o que cobre as conexões concorrentes. Swagger automático cobre a documentação | Flask (síncrono), Node/Express (Swagger manual) |
| Protocolo | **REST (JSON sobre HTTPS)** | Corresponde ao "cliente HTTP" do enunciado; testável com `curl` e Swagger; simples de explicar | WebSocket, SSE |
| LLM | **Qwen3** (open weight, Alibaba): `qwen3.8-27b` no Groq e `Qwen3-32B` na DeepInfra | Modelo aberto de boa qualidade em português, com contexto amplo e custo zero ou baixo | GPT/Gemini (proprietários e pagos), rodar local (inviável na EC2) |
| Provedor | **Groq** (principal, free tier) e **DeepInfra** (reserva paga) | Groq é gratuito e tem latência muito baixa; DeepInfra elimina o risco de rate limit na demo | OpenRouter free (limite menor, latência variável) |
| SDK | **`openai` (Python, AsyncOpenAI)** | Groq e DeepInfra expõem API compatível com OpenAI, então trocar de provedor é só mudar o `.env` | LangChain (camada desnecessária para chat simples) |
| Sessões | **Memória do processo**, atrás da interface `SessionStore` | Simples e rápido; a interface permite trocar por Redis sem mexer nas rotas | Redis, SQLite |
| Front-end | **React + Vite** | Componentização e estado de chat claros; o build estático é servido pelo Nginx no mesmo domínio (sem CORS) | HTML puro, sem front |
| Infra | **EC2 + Docker Compose + Nginx + Let's Encrypt** | Ambiente igual em dev e prod; HTTPS no domínio do Pedro; deploy com um comando | systemd sem Docker |

---

## 3. Arquitetura

```
 Navegadores (React)  ×N usuários
        │  HTTPS
        ▼
 ┌────────────────── EC2 (Ubuntu 24.04, Docker Compose) ──────────────────┐
 │  container "web": Nginx                                                 │
 │     /           → arquivos estáticos do build do React                  │
 │     /api/*      → proxy_pass http://api:8000                            │
 │                                                                         │
 │  container "api": Uvicorn (1 worker) + FastAPI                          │
 │     routes/     → endpoints REST, validação Pydantic, erros             │
 │     sessions/   → SessionStore em memória (locks + TTL + limite)        │
 │     llm/        → LLMClient (AsyncOpenAI) + prompts das personas        │
 └──────────────────────────────────┬──────────────────────────────────────┘
                                    │ HTTPS
                                    ▼
            Groq (Qwen3.8-27B)  │  DeepInfra (Qwen3-32B, via .env)
```

### 3.1 Estrutura do repositório

Repositório `chatbot-multiusuario-tca`, criado pelo Izaías na conta dele, com os outros 3 como colaboradores com permissão de escrita.

```
chatbot-multiusuario-tca/
├── backend/
│   ├── app/
│   │   ├── main.py            # cria o app, registra rotas, handlers, tarefa de limpeza
│   │   ├── config.py          # Settings (pydantic-settings) lidas do .env
│   │   ├── schemas.py         # modelos Pydantic do contrato (seção 5)
│   │   ├── errors.py          # exceções de domínio + handlers → formato de erro
│   │   ├── routes/sessions.py # endpoints /api/sessions...
│   │   ├── sessions/store.py  # SessionStore, Session, Message
│   │   └── llm/
│   │       ├── client.py      # LLMClient
│   │       └── personas.py    # system prompts por persona
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # projeto Vite + React
│   ├── src/
│   │   ├── api/client.js      # funções que chamam a API
│   │   ├── components/        # StartScreen, ChatWindow, MessageList, MessageInput, SessionBadge
│   │   └── App.jsx
│   ├── vite.config.js         # proxy /api → http://localhost:8000 em dev
│   └── package.json
├── infra/
│   ├── nginx/default.conf     # produção (HTTPS)
│   ├── nginx/local.conf       # versão local, só HTTP (seção 7.3)
│   └── web.Dockerfile         # multi-stage: build do React (node) → nginx
├── scripts/
│   ├── concurrency_test.py    # teste de N usuários simultâneos (seção 8.3)
│   └── smoke_test.sh          # verificação pós-deploy (seção 8.4)
├── docs/
│   ├── superpowers/specs/     # esta spec
│   └── escolha-do-modelo.md   # comparação de modelos (seção 8.5)
├── docker-compose.yml
├── docker-compose.local.yml
├── .env.example
└── README.md                  # visão geral, como rodar, documentação da API
```

---

## 4. Módulos do backend

Cada módulo tem uma responsabilidade e uma interface pequena, de modo que pode ser desenvolvido e testado sem os outros.

### 4.1 `sessions/store.py`: SessionStore (dona: Maria Eduarda)

```python
@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime            # UTC

@dataclass
class Session:
    id: str                         # uuid4 em string
    persona: Literal["geral", "juridico"]
    created_at: datetime
    last_activity: datetime
    messages: list[Message]
    lock: asyncio.Lock              # serializa perguntas da MESMA sessão

class SessionStore:
    async def create(self, persona: str) -> Session
    async def get(self, session_id: str) -> Session          # levanta SessionNotFound
    async def append_exchange(self, session_id: str, user: Message, assistant: Message) -> None
    async def delete(self, session_id: str) -> None          # levanta SessionNotFound
    async def cleanup_expired(self) -> int                   # devolve quantas removeu
    def count(self) -> int
```

**Regras:**
- **Dicionário compartilhado:** `dict[str, Session]`, protegido por um `asyncio.Lock` global apenas durante leituras e escritas no dicionário (operações rápidas, sem `await` de rede).
- **Lock por sessão:** `Session.lock` é segurado durante toda a pergunta (montar contexto, chamar o LLM, gravar). Perguntas simultâneas na mesma sessão ficam em fila e o histórico mantém a ordem. Sessões diferentes não se bloqueiam.
- **Expiração (TTL):** uma sessão expira quando `agora - last_activity > SESSION_TTL_MIN`. Uma tarefa de fundo (`asyncio.create_task` no *lifespan* do app) chama `cleanup_expired()` a cada 60 s. Sessões com `lock.locked()` são puladas para não remover uma sessão no meio de uma resposta.
- **Limite de sessões:** ao criar a sessão de número `SESSION_MAX + 1`, remove-se a de `last_activity` mais antiga que não esteja com o lock ocupado.
- **Limite com todas as sessões ocupadas:** se todas estiverem com o lock ocupado, a nova sessão é criada mesmo assim e o limite é excedido temporariamente.
- **Relógio injetável:** o construtor é `SessionStore(clock: Callable[[], datetime] = utcnow)`, para os testes controlarem o tempo.
- **`last_activity`:** é renovado por `get(id, touch=True)`, chamado pela rota de mensagem, e por `append_exchange`. O `GET` de histórico usa `touch=False` e não renova.
- **Histórico consistente:** `append_exchange` grava pergunta e resposta juntas. Se o LLM falhar, nada é gravado e o histórico não fica com pergunta sem resposta.
- **Sessão removida durante uma pergunta:** o `DELETE` remove a sessão mesmo com o lock ocupado. Se o ID não estiver mais no dicionário (por `DELETE`, expiração ou limite), `append_exchange` levanta `SessionNotFound`; a rota responde 404 e descarta a resposta do LLM.

### 4.2 `llm/client.py`: LLMClient (dono: Eduardo)

```python
class LLMClient:
    def __init__(self, settings: Settings): ...
    async def chat(self, persona: str, history: list[Message], question: str) -> str
        # levanta LLMTimeout ou LLMUnavailable
```

**Regras:**
- **Cliente:** `AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT_S, max_retries=0)`. O retry embutido do SDK fica desligado; vale apenas o nosso.
- **Montagem do contexto:** `[system prompt da persona] + últimas HISTORY_WINDOW mensagens do histórico + {"role":"user","content":question}`.
- **Parâmetros:** `model=LLM_MODEL`, `temperature=LLM_TEMPERATURE`, `max_tokens=LLM_MAX_TOKENS` e `extra_body=LLM_EXTRA_BODY`. O código não testa qual é o provedor: parâmetros específicos vêm só do `.env`.
- **Mapeamento de exceções do SDK:** capturar `APITimeoutError` antes de `APIConnectionError`, porque a primeira é subclasse da segunda.
  - `APITimeoutError` → `LLMTimeout`, **sem retry**.
  - `RateLimitError` (429), `APIStatusError` com status ≥ 500 e `APIConnectionError` → até `LLM_MAX_RETRIES` novas tentativas, com espera de 1 s e depois 2 s. Esgotadas as tentativas, `LLMUnavailable`.
  - Qualquer outro 4xx (401 chave inválida, 403, 400 parâmetro inválido, 404 modelo inexistente) → `LLMUnavailable` **sem retry**, com log ERROR do status e do corpo da resposta do provedor.
- **Modo de raciocínio do Qwen3:** desligado pelo *soft switch* `/no_think` no fim do system prompt (vale em qualquer provedor). Como garantia, remover `<think>.*?</think>` (regex com DOTALL) e também um `<think>` sem fechamento até o fim do texto; depois aplicar `.strip()`.
- **Resposta vazia:** se o texto vier vazio após a limpeza, levanta `LLMUnavailable`.

### 4.3 `llm/personas.py`: prompts (dono: Eduardo)

```python
PERSONAS = {
  "geral": (
    "Você é um assistente virtual prestativo. Responda sempre em português do Brasil, "
    "de forma clara, correta e objetiva. Se não souber algo, diga que não sabe. "
    "Use listas curtas quando ajudar a leitura. /no_think"
  ),
  "juridico": (
    "Você é um assistente de orientação jurídica geral sobre o direito brasileiro. "
    "Responda em português do Brasil, em linguagem acessível, citando a lei quando "
    "souber com segurança. Deixe claro que a resposta é informativa e não substitui "
    "um advogado; quando o caso for concreto, recomende procurar um advogado ou a "
    "Defensoria Pública. /no_think"
  ),
}
```

O texto final dos prompts pode ser ajustado pelo Eduardo após a comparação de modelos (seção 8.5). Duas coisas são fixas: as chaves `geral` e `juridico`, que fazem parte do contrato, e o `/no_think` no fim de cada prompt.

### 4.4 Restrição: 1 processo da API

Como as sessões ficam na memória do processo, o Uvicorn roda com **1 worker**. A concorrência vem do asyncio (milhares de requisições aguardando I/O no mesmo processo), não de vários processos. Para escalar horizontalmente seria preciso trocar o `SessionStore` por Redis; esse é o argumento da interface trocável e deve ser citado na apresentação.

### 4.5 `routes/sessions.py` e `errors.py` (dona: Maria Eduarda)

`SessionStore` e `LLMClient` são instâncias únicas, criadas no *lifespan* e injetadas via `Depends`. Isso permite substituir o `LLMClient` por um `FakeLLM` nos testes.

**Fluxo de `POST /api/sessions/{id}/messages`:**
1. O Pydantic valida o corpo; se for inválido, responde 422 `invalid_request`. O `content` é gravado já com `strip()`, e o `created_at` da mensagem do usuário é o momento em que ela foi recebida.
2. `store.get(id, touch=True)`; se não existir, responde 404 `session_not_found`. O `session_id` do caminho é declarado como `str`, então um ID malformado também resulta em 404, e não em 422.
3. Todo este passo roda dentro de `asyncio.timeout(LLM_TOTAL_TIMEOUT_S)`; se estourar, a rota responde 504 `llm_timeout` e nada é gravado:
   1. `async with session.lock:` (espera na fila da sessão).
   2. `reply = await llm.chat(session.persona, session.messages, content)`.
   3. `store.append_exchange(id, user_msg, assistant_msg)`.
4. Responde 200 com `session_id` e `reply`.

`LLMTimeout` vira 504 `llm_timeout`, e `LLMUnavailable` vira 503 `llm_unavailable`. Exceções inesperadas viram 500 `internal_error`, com log do stack trace e sem vazar detalhes para o cliente. O handler de `RequestValidationError` do FastAPI é sobrescrito para devolver o formato de erro padrão.

---

## 5. Contrato da API

- Base: `https://<domínio>/api`; em desenvolvimento, `http://localhost:8000/api`.
- Corpo em JSON, UTF-8. Datas em ISO 8601 UTC (`2026-11-11T14:00:00Z`).
- Swagger: `/api/docs`. OpenAPI: `/api/openapi.json`.

| Método | Rota | Sucesso | Erros possíveis |
|---|---|---|---|
| `GET` | `/api/health` | 200 | — |
| `POST` | `/api/sessions` | 201 | 422 |
| `GET` | `/api/sessions/{session_id}` | 200 | 404 |
| `POST` | `/api/sessions/{session_id}/messages` | 200 | 404, 422, 503, 504 |
| `DELETE` | `/api/sessions/{session_id}` | 204 | 404 |

### 5.1 `GET /api/health`
```json
200 { "status": "ok", "active_sessions": 3, "model": "qwen/qwen3.8-27b" }
```

### 5.2 `POST /api/sessions`: conectar
Requisição (o corpo é opcional; sem corpo, vale `"geral"`):
```json
{ "persona": "geral" }
```
Resposta:
```json
201 { "session_id": "3f2a9c1e-8b7d-4c1a-9e2f-0a1b2c3d4e5f", "persona": "geral", "created_at": "2026-11-11T14:00:00Z" }
```

### 5.3 `GET /api/sessions/{session_id}`: histórico
```json
200 {
  "session_id": "3f2a9c1e-…",
  "persona": "geral",
  "created_at": "2026-11-11T14:00:00Z",
  "last_activity": "2026-11-11T14:02:10Z",
  "messages": [
    { "role": "user", "content": "O que é computação em nuvem?", "created_at": "2026-11-11T14:02:05Z" },
    { "role": "assistant", "content": "Computação em nuvem é…", "created_at": "2026-11-11T14:02:10Z" }
  ]
}
```
`messages` devolve o histórico completo da sessão. Só as últimas `HISTORY_WINDOW` mensagens vão para o LLM.

### 5.4 `POST /api/sessions/{session_id}/messages`: perguntar
Requisição (`content` com 1 a `MESSAGE_MAX_CHARS` caracteres após `strip()`):
```json
{ "content": "O que é computação em nuvem?" }
```
Resposta:
```json
200 {
  "session_id": "3f2a9c1e-…",
  "reply": { "role": "assistant", "content": "Computação em nuvem é…", "created_at": "2026-11-11T14:02:10Z" }
}
```

### 5.5 `DELETE /api/sessions/{session_id}`: encerrar
`204` sem corpo.

### 5.6 Formato de erro
```json
{ "error": { "code": "session_not_found", "message": "Sessão não encontrada ou expirada." } }
```

| HTTP | `code` | Quando | `message` (texto exibido pelo front) |
|---|---|---|---|
| 404 | `session_not_found` | ID inexistente, expirado ou removido | Sessão não encontrada ou expirada. |
| 422 | `invalid_request` | Corpo inválido, `content` vazio ou longo demais, persona inválida | Requisição inválida: <detalhe do campo> |
| 503 | `llm_unavailable` | Rate limit ou erro do provedor após retries, chave inválida, resposta vazia | O modelo está indisponível no momento. Tente novamente. |
| 504 | `llm_timeout` | Uma tentativa passou de `LLM_TIMEOUT_S`, ou a requisição inteira passou de `LLM_TOTAL_TIMEOUT_S` | O modelo demorou demais para responder. Tente novamente. |
| 500 | `internal_error` | Erro inesperado | Erro interno do servidor. |

### 5.7 Segurança do ID

- Não existe rota que liste IDs de sessões. O `session_id` (UUID v4, 122 bits aleatórios) funciona como um token: só quem o conhece acessa a conversa.
- O ID completo nunca aparece em logs. O Uvicorn roda com `--no-access-log`, e o Nginx usa `access_log off;` em `location /api/`.
- A aplicação registra em INFO, usando só os 8 primeiros caracteres do ID: `session_created sess=3f2a9c1e persona=geral`, `message sess=3f2a9c1e status=200 latency_ms=1834 attempts=1`, `session_deleted sess=3f2a9c1e` e `cleanup removed=N`. São esses logs que aparecem na demo.

---

## 6. Front-end (dono: Izaías)

**Telas e componentes:**
- **`StartScreen`:** escolha da persona ("Assistente geral" ou "Orientação jurídica") e botão "Iniciar conversa", que chama `POST /api/sessions`.
- **`ChatWindow`:** contém `SessionBadge`, `MessageList` e `MessageInput`.
- **`SessionBadge`:** mostra os 8 primeiros caracteres do `session_id` e a persona. Ao clicar, copia o ID completo. Serve para provar na demo que cada aba tem o seu ID.
- **`MessageList`:** balões de usuário e assistente, com rolagem automática para a última mensagem. O conteúdo do assistente é renderizado como Markdown com `react-markdown`, sem `rehype-raw`, para que HTML vindo do modelo não seja interpretado. As mensagens do usuário são texto puro com `white-space: pre-wrap`.
- **`MessageInput`:** textarea em que Enter envia e Shift+Enter quebra linha, com contador de caracteres (máximo 2000). Fica desabilitado enquanto aguarda resposta e mostra o indicador "digitando…".
- **Botão "Nova conversa":** chama `DELETE` na sessão atual (ignorando um 404), limpa o estado e volta para `StartScreen`.

**Comportamento:**
- O `session_id` fica em `sessionStorage`: cada aba é um usuário diferente e um F5 mantém a conversa.
- Ao carregar a página com um ID salvo, o front chama `GET /api/sessions/{id}` para recarregar o histórico. Se receber 404, apaga o ID e mostra `StartScreen` com o aviso "Sua sessão expirou".
- A mensagem do usuário aparece na lista imediatamente. Se o envio falhar, ela fica marcada com erro e um botão "Tentar de novo" reenvia o mesmo texto.
- Erros 422, 503, 504 e 500 exibem a `message` da API. O 404 durante o chat leva ao fluxo de sessão expirada.
- Exceção de rede no `fetch` ou corpo que não é JSON (ex.: 502 em HTML do Nginx enquanto o container `api` reinicia) exibe "Não foi possível falar com o servidor. Tente novamente." com o botão "Tentar de novo".
- `src/api/client.js` é o único lugar que faz `fetch`. Todas as URLs são relativas (`/api/...`).
- O limite do contador de caracteres é uma constante `MAX_CHARS = 2000` no front e deve ser mantido igual a `MESSAGE_MAX_CHARS`.
- Em desenvolvimento, `vite.config.js` faz proxy de `/api` para `http://localhost:8000`.
- O layout deve funcionar no celular (largura mínima de 360px), porque a turma vai acessar pelo QR code.

---

## 7. Infraestrutura e deploy (dono: Pedro)

### 7.1 Configuração (`.env`, nunca versionado; o `.env.example` é versionado)

| Variável | Valor padrão / exemplo | Uso |
|---|---|---|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint compatível com OpenAI |
| `LLM_API_KEY` | (secreto) | Chave do provedor |
| `LLM_MODEL` | `qwen/qwen3.8-27b` | ID do modelo no provedor |
| `LLM_EXTRA_BODY` | `{}` | JSON repassado como `extra_body` (no Groq: `{"reasoning_effort":"none"}`) |
| `LLM_TIMEOUT_S` | `20` | Timeout por tentativa |
| `LLM_TOTAL_TIMEOUT_S` | `60` | Limite da requisição inteira: fila do lock + tentativas + esperas |
| `LLM_MAX_RETRIES` | `2` | Retries em 429, 5xx e erro de conexão |
| `LLM_MAX_TOKENS` | `1024` | Tamanho máximo da resposta |
| `LLM_TEMPERATURE` | `0.7` | Criatividade |
| `SESSION_TTL_MIN` | `30` | Inatividade até expirar |
| `SESSION_MAX` | `1000` | Máximo de sessões simultâneas |
| `HISTORY_WINDOW` | `20` | Mensagens enviadas ao LLM |
| `MESSAGE_MAX_CHARS` | `2000` | Tamanho máximo da pergunta |

**Provedor por fase:** o desenvolvimento usa o **Groq** (gratuito). Em 10/11 a produção troca para a **DeepInfra**, e a apresentação roda nela, para eliminar o risco de rate limit com a turma acessando: `LLM_BASE_URL=https://api.deepinfra.com/v1/openai`, `LLM_MODEL=Qwen/Qwen3-32B`, `LLM_EXTRA_BODY={}`. O Eduardo confirma os IDs exatos nos painéis do Groq e da DeepInfra até 05/11, atualiza o `.env.example` e carrega US$ 5 de crédito na DeepInfra até 09/11.

**Modelo no Groq:** o Groq desligou o `qwen/qwen3-32b` em 17/07/2026. No desenvolvimento, usa-se o `qwen/qwen3.8-27b` (preview), com o raciocínio desligado por `reasoning_effort: none` no `LLM_EXTRA_BODY`. A DeepInfra continua com o `Qwen/Qwen3-32B`.

**Limites do Groq:** até 05/11, o Eduardo registra no README os limites do free tier do Groq para o modelo: requisições por minuto, tokens por minuto e requisições por dia. Se 10 usuários × 2 mensagens não couberem no limite de tokens por minuto, o marco de 08/11 roda com `--users 5`, e o teste com `--users 10` fica para 10/11, já na DeepInfra. No relatório do `concurrency_test.py`, um 503 causado por rate limit do provedor aparece como "rate limit do provedor", separado de uma falha de isolamento.

### 7.2 Containers (`docker-compose.yml`)

- **`api`:** build de `backend/Dockerfile` (python:3.12-slim). Comando `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`, `env_file: .env`, `restart: unless-stopped`. Não publica porta para fora (só a rede interna do Compose).
- **`web`:** build de `infra/web.Dockerfile`. O estágio 1 (`node:20`) roda `npm ci && npm run build`; o estágio 2 (`nginx:alpine`) copia `dist/` e `default.conf`. Publica as portas 80 e 443 e monta `/etc/letsencrypt` do host em modo somente leitura. `restart: unless-stopped`.

### 7.3 Nginx (`infra/nginx/default.conf`)

- A porta 80 redireciona para 443.
- A porta 443 usa os certificados de `/etc/letsencrypt/live/<domínio>/`.
- `location /api/` faz `proxy_pass http://api:8000;` com `proxy_read_timeout 90s`, com folga sobre o `LLM_TOTAL_TIMEOUT_S` de 60 s. Assim, o backend sempre responde no formato do contrato antes de o Nginx cortar a conexão.
- `location /` serve os estáticos com `try_files $uri /index.html`.
- **Versão local, sem HTTPS:** `infra/nginx/local.conf` (só porta 80, mesmas `location`) e `docker-compose.local.yml`, que monta esse arquivo e publica `8080:80`. Uso: `docker compose -f docker-compose.yml -f docker-compose.local.yml up --build`. Essa é a alternativa caso a EC2 caia (seção 12).

### 7.4 EC2

- Instância **t3.small** (2 GB de RAM, necessária para o `npm run build` no host), Ubuntu 24.04, disco de 20 GB.
- **Elastic IP** associado e registro DNS **A** do subdomínio `chat.` no domínio do Pedro (o nome final é escolhido por ele e registrado no README até 06/11).
- **Security Group:** porta 22 só para os IPs da equipe; portas 80 e 443 abertas para 0.0.0.0/0.
- **HTTPS:** emissão com `certbot certonly --standalone` antes de subir o Nginx. Não há renovação: o certificado vale 90 dias e a instância vive menos de uma semana.
- **Deploy:** `git pull && docker compose up -d --build`, documentado no README.
- **Custo:** a instância fica ligada de 06/11 a 11/11 e é desligada depois da nota.

---

## 8. Testes e verificação

### 8.1 Backend (Maria Eduarda): `pytest`, `pytest-asyncio`, `httpx.AsyncClient`
- **SessionStore:**
  - Cria sessões com IDs únicos.
  - `get` de ID inexistente levanta `SessionNotFound`.
  - A sessão expira após o TTL (com relógio injetável).
  - Respeita o limite `SESSION_MAX`.
  - A limpeza não remove sessão com lock ocupado.
- **Rotas** (com `FakeLLM` que devolve `"eco: <pergunta>"`): todos os códigos de sucesso e erro da seção 5, conferindo o formato de erro.
- **Concorrência determinística:** com um `FakeLLM` que faz `await asyncio.sleep(1)`, 10 sessões perguntando em paralelo terminam em menos de 3 s no total (prova que não serializa) e cada resposta contém a pergunta da própria sessão (prova o isolamento).
- **Ordem na mesma sessão:** 2 perguntas simultâneas na mesma sessão resultam em histórico `[user1, assistant1, user2, assistant2]`, e a 2ª chamada ao `FakeLLM` recebe a 1ª troca no histórico.
- **DELETE durante uma pergunta:** com o `FakeLLM` lento, a pergunta em andamento termina em 404.
- **Timeout total:** com `LLM_TOTAL_TIMEOUT_S=1` e um `FakeLLM` de 2 s, a rota responde 504 e o histórico continua vazio.

### 8.2 LLMClient (Eduardo): `pytest` com o cliente HTTP mockado (`respx`)
- Monta o contexto com o system prompt certo e as últimas `HISTORY_WINDOW` mensagens.
- Um 429 seguido de 200 resulta em sucesso (2 chamadas). 3 respostas 429 levantam `LLMUnavailable` (3 chamadas).
- Timeout levanta `LLMTimeout` (1 chamada). 401 e 404 levantam `LLMUnavailable` (1 chamada). O número de chamadas é conferido no `respx`.
- Remove `<think>…</think>` e também `<think>` sem fechamento; resposta vazia levanta `LLMUnavailable`.

### 8.3 Script de concorrência (Eduardo): `scripts/concurrency_test.py`
- Uso: `python scripts/concurrency_test.py --base-url https://<domínio> --users 10`.
- Cada usuário simulado `i` cria uma sessão e envia, em paralelo com os outros, "Meu nome é <Nome_i>. Guarde isso." e em seguida "Qual é o meu nome? Responda só o nome."
- Os nomes são distintos e incomuns (ex.: Aurélio, Benedita, Cassiano…) para evitar acertos por acaso.
- Uma resposta é OK quando, normalizada (minúsculas, sem acentos), contém o nome esperado e nenhum dos outros nomes do teste.
- O script imprime uma tabela (usuário, ID curto, nome esperado, resposta, latência, OK/FALHA) e termina com código 1 se alguma resposta não for OK ou se houver erro HTTP.

### 8.4 Smoke test pós-deploy (Pedro): `scripts/smoke_test.sh <url>`
Com `curl` e `jq`: `GET /api/health` responde 200, `POST /api/sessions` responde 201, `POST .../messages` responde 200 com `reply.content` não vazio, e `GET /` responde 200 com HTML. Roda após todo deploy.

### 8.5 Escolha do modelo (Eduardo): `docs/escolha-do-modelo.md`
- 10 perguntas fixas em português (conhecimento geral, explicação técnica, raciocínio simples, 2 jurídicas, 1 de continuidade de contexto).
- Pelo menos 3 modelos disponíveis no provedor; um deles é obrigatoriamente um Qwen3 (`qwen3.8-27b` no Groq ou `Qwen3-32B` na DeepInfra).
- A tabela registra latência média e uma nota de qualidade de 1 a 5 dada pela equipe.
- Termina com uma conclusão de um parágrafo que serve de base ao slide de justificativa.

### 8.6 Front-end (Izaías): Vitest + Testing Library, com `fetch` mockado
- **Início de sessão:** criar sessão salva o ID no `sessionStorage` e mostra o `SessionBadge`.
- **Envio:** enviar mensagem renderiza a resposta, e o input fica desabilitado enquanto aguarda.
- **Markdown:** uma resposta com `**x**` renderiza `<strong>x</strong>`; uma resposta com `<script>` aparece como texto e não é executada.
- **Erros:** um 404 ao recarregar volta para `StartScreen` com o aviso; um 503 mostra a mensagem de erro e o botão "Tentar de novo"; uma exceção de rede mostra a mensagem genérica.

### 8.7 Checklist manual do front (Izaías, no ensaio de 10/11, contra produção)
- F5 mantém o histórico.
- Duas abas mostram IDs diferentes.
- "Nova conversa" volta para a `StartScreen`.
- Enter envia e Shift+Enter quebra linha.
- O layout funciona em 360px (no DevTools e em um celular real).
- Com `SESSION_TTL_MIN=1` rodando localmente, a sessão expira e aparece "Sua sessão expirou".

---

## 9. Divisão de tarefas

Regra de equilíbrio: **cada integrante tem 1 módulo de código, os testes desse módulo, 1 entrega transversal e 1 trecho da apresentação.** Os dois módulos mais densos de lógica (sessões e LLM) ficam com pessoas diferentes. Infra e front-end têm porte equivalente, cada um com sua curva de aprendizado (AWS/DNS/HTTPS e React do zero).

| | **Pedro** | **Izaías** | **Maria Eduarda** | **Eduardo** |
|---|---|---|---|---|
| **Módulo** | `backend/Dockerfile`, `infra/`, `docker-compose.yml` (seção 7) | `frontend/` (seção 6) | `app/main.py`, `config.py`, `schemas.py`, `errors.py`, `routes/`, `sessions/` (seções 4.1, 4.4, 4.5) | `app/llm/` (seções 4.2, 4.3) |
| **Testes** | `smoke_test.sh` (8.4) | Vitest (8.6) | pytest do store e das rotas (8.1) | pytest do LLMClient (8.2) + `concurrency_test.py` (8.3) |
| **Entrega transversal** | EC2, Security Group, Elastic IP, DNS, HTTPS (7.4) | Repositório, board de tasks, template de PR, proteção da `main` | Stub da API no dia 1 (rotas do contrato com respostas fixas) | README: documentação da API com `curl` + `docs/escolha-do-modelo.md` (8.5) |
| **README (seção própria)** | "Deploy" | "Front-end: como rodar" | "Backend: como rodar e testar" | "API" e "Modelo LLM" |
| **Apresentação** | Infra e deploy, com o console AWS ao vivo | Front e condução da demo multiusuário | Abertura, arquitetura, sessões e concorrência | Escolha do LLM, prompts e o script de concorrência ao vivo |

### 9.1 Regras de colaboração

- **Branches:** `feat/<area>-<descricao>` (ex.: `feat/sessions-ttl`). Ninguém faz push direto na `main`.
- **PRs:** precisam de 1 aprovação, no rodízio: **Pedro revisa Maria Eduarda, Maria Eduarda revisa Eduardo, Eduardo revisa Izaías, Izaías revisa Pedro.** O revisor deve rodar o código e os testes localmente antes de aprovar.
- **Board:** as tasks do board (criado pelo Izaías) correspondem às linhas da tabela acima, uma por célula de "Módulo", "Testes" e "Entrega transversal".
- **Check-in diário no grupo, às 21h:** "fiz / vou fazer / bloqueio". Um bloqueio que dure mais de 24 h é redistribuído em call.
- **Segredos:** a chave do LLM é compartilhada só no grupo de WhatsApp e nunca entra no git. O `.env` está no `.gitignore` desde o primeiro commit.

---

## 10. Cronograma

| Data | Marco | Critério de "pronto" |
|---|---|---|
| **qua 04/11** | Call de alinhamento; spec aprovada; repositório e board criados (Izaías) | Os 4 conseguem clonar o repositório e veem suas tasks |
| **qui 05/11** | Stub da API na `main` (Maria Eduarda); IDs dos modelos confirmados (Eduardo) | `uvicorn` sobe localmente e as 5 rotas respondem com o formato do contrato |
| **qui 05 – sex 06** | Desenvolvimento de cada módulo com mocks; EC2 + HTTPS servindo o stub (Pedro) | `https://<domínio>/api/health` responde 200 |
| **sáb 07/11** | Integração do backend: store real + LLMClient real; primeiro deploy completo | `smoke_test.sh` passa contra a EC2 |
| **dom 08/11** | Front integrado com a API em produção; script de concorrência contra a EC2 | `concurrency_test.py` termina com tudo OK em produção, com `--users 10` ou `--users 5` se o limite do Groq exigir (seção 7.1) |
| **seg 09/11** | Correções, README completo, `escolha-do-modelo.md`, slides; teste de troca para DeepInfra | Todos os testes passam; a troca de provedor pelo `.env` foi testada em produção |
| **ter 10/11** | Produção passa a usar a DeepInfra; **congelamento do código** às 18h; ensaio completo de 30 min; checklist 8.7; teste da versão local | Cada integrante explica em 1 min a parte de outro integrante; `concurrency_test.py` termina com tudo OK na DeepInfra |
| **qua 11/11** | Apresentação | — |

---

## 11. Apresentação (30 min)

| Min | Bloco | Quem |
|---|---|---|
| 0–2 | Problema, requisitos e arquitetura geral | Maria Eduarda |
| 2–7 | Sessões, IDs únicos, locks, TTL, por que FastAPI/async, por que 1 worker | Maria Eduarda |
| 7–12 | Escolha do Qwen3 (tabela comparativa), prompts e personas, tratamento de erros do LLM | Eduardo |
| 12–17 | Front-end React, fluxo de sessão no navegador | Izaías |
| 17–22 | Infra AWS: EC2, Docker Compose, Nginx, HTTPS, domínio | Pedro |
| 22–26 | **Demo ao vivo:** 3 abas com IDs diferentes e personas diferentes; QR code para a turma usar; `concurrency_test.py` rodando contra produção; Swagger em `/api/docs` | Izaías conduz, Eduardo roda o script, Pedro mostra os logs do container |
| 26–30 | Perguntas | Todos |

O QR code aponta para `https://<domínio>` e entra no slide da demo.

---

## 12. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Rate limit do Groq durante a demo (turma inteira acessando) | A demo roda na DeepInfra, paga, desde 10/11 (seção 7.1); o crédito pré-pago limita o custo |
| Wi-Fi da sala instável | Roteador do celular de um integrante como alternativa; vídeo gravado da demo (gravado em 10/11) |
| EC2 ou DNS fora do ar | Versão local (seção 7.3) no notebook da apresentação, ensaiada em 10/11 |
| Qwen3 devolvendo `<think>` ou respostas em inglês | `/no_think` + remoção por regex; o system prompt exige português |
| Integrante atrasado | Check-in diário; bloqueio de mais de 24 h é redistribuído em call; o rodízio de revisão garante que outra pessoa conhece o código |
| Professor pergunta sobre a parte de outra pessoa | Revisão cruzada de PRs + rodada de explicações cruzadas no ensaio de 10/11 |

---

## 13. Critérios de aceite (mapeados aos critérios de avaliação)

| Critério do professor | Como demonstramos |
|---|---|
| Funcionamento correto do chatbot multiusuário | Demo com várias abas e a turma via QR code; `concurrency_test.py` com tudo OK |
| Gestão adequada das sessões por ID único | UUID v4 gerado no `POST /api/sessions`; `SessionBadge` visível; testes 8.1 |
| Qualidade e coerência das respostas do LLM | `docs/escolha-do-modelo.md`; teste de continuidade de contexto (nome) |
| Implantação funcional na AWS EC2 | `https://<domínio>` no ar; console AWS mostrado ao vivo |
| Acessibilidade pública | HTTPS em domínio público; `smoke_test.sh` contra produção |
| Organização e clareza do código | Módulos com interfaces pequenas (seção 4); PRs revisados; README por seção |
| Conexões concorrentes | Teste determinístico de concorrência (8.1) + script contra produção (8.3) |
| Justificativa técnica de LLM e framework | Seção 2 + slides de Maria Eduarda (stack) e Eduardo (LLM) |
| Código no GitHub | Repositório `chatbot-multiusuario-tca` com histórico de commits dos 4 |
