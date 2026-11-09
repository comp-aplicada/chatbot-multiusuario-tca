# Plano do front-end (Izaías)

> Itens marcados com `[x]` já foram executados. Primeiro passo pendente: **Fase 0, item "Mandar no grupo o link do repo e do board"**, e depois abrir o PR da Fase 1.

- **Dono:** Izaías de Melo Lima Morais
- **Revisor dos PRs:** Eduardo (rodízio da seção 9.1 do PRD)
- **Referências:** [PRD](prd-chatbot-multiusuario.md) seções 5 (contrato), 6 (front-end), 8.6 e 8.7 (testes), 9 (divisão), 11 (apresentação); [enunciado](tarefa.md)
- **Apresentação:** quinta, 26/11/2026
- **Board:** projeto "Chatbot Multiusuário TCA" na org `comp-aplicada`, milestone "Apresentação (26/11)"

> Atenção: o cronograma do PRD foi escrito para apresentação em 11/11. A apresentação é em **26/11**, então a seção 9 deste plano usa o cronograma novo, o mesmo das datas de entrega das issues.

---

## 1. Objetivo

Entregar uma interface web de chat, servida no mesmo domínio da API, que:

1. Cria uma sessão (UUID v4) ao clicar em "Iniciar conversa" e mostra o ID na tela.
2. Envia perguntas e mostra as respostas do LLM, mantendo o histórico daquela sessão.
3. Trata cada aba do navegador como um usuário diferente, o que é a base da demo multiusuário.
4. Sobrevive a F5, sessão expirada, erro do modelo e queda da API sem quebrar a tela.
5. Funciona no celular a partir de 360px de largura, porque a turma vai entrar pelo QR code.

### Fora do escopo

- Login, cadastro, lista de conversas antigas, streaming, upload de arquivos, tema escuro.
- Qualquer lógica de sessão no cliente além de guardar o `session_id` no `sessionStorage`.

---

## 2. Stack

| Item | Escolha | Motivo |
|---|---|---|
| Build | **Vite** | Definido no PRD; dev server rápido e proxy de `/api` embutido |
| UI | **React 19** (`.tsx`) | Definido no PRD; estado de chat simples de explicar na apresentação |
| Linguagem | **TypeScript 7** com `strict` e `noUncheckedIndexedAccess` | O contrato da API vira tipo, então campo errado ou persona inválida quebra na compilação e não na demo. Proibido `any` (regra `typescript/no-explicit-any` no oxlint) |
| Estilo | **Tailwind CSS v4** (`@tailwindcss/vite`) | Responsivo sem escrever CSS à mão; só escala padrão, nada de valores arbitrários em px |
| Markdown | **react-markdown** (sem `rehype-raw`) | HTML vindo do modelo vira texto, não é interpretado (PRD 6) |
| Testes | **Vitest + @testing-library/react + jsdom** | Definido no PRD 8.6 |
| Lint | **oxlint** (padrão do template Vite atual) | Organização do código conta na nota |
| Node | **20.19 ou mais novo** (exigência do Vite 8) | Mesmo do estágio de build do `infra/web.Dockerfile` (PRD 7.2) |

---

## 3. Estrutura de pastas

```
frontend/
├── index.html
├── package.json
├── tsconfig.json             # referências para tsconfig.app.json (src e tests) e tsconfig.node.json (vite.config.ts)
├── vite.config.ts            # proxy /api -> http://localhost:8000 e config do Vitest
├── src/
│   ├── main.tsx
│   ├── App.tsx               # decide entre StartScreen e ChatWindow
│   ├── index.css             # @import "tailwindcss"
│   ├── constants.ts          # MAX_CHARS, PERSONAS, STORAGE_KEY, mensagens fixas
│   ├── api/
│   │   ├── client.ts         # ÚNICO lugar com fetch
│   │   └── types.ts          # tipos do contrato da API (seção 5 do PRD)
│   ├── state/
│   │   └── chatReducer.ts    # estado e ações da conversa
│   └── components/
│       ├── StartScreen.tsx
│       ├── ChatWindow.tsx
│       ├── SessionBadge.tsx
│       ├── MessageList.tsx
│       ├── MessageBubble.tsx
│       └── MessageInput.tsx
└── tests/
    ├── setup.ts
    ├── client.test.ts
    ├── startSession.test.tsx
    ├── sendMessage.test.tsx
    ├── markdown.test.tsx
    └── errors.test.tsx
```

---

## 4. Camada de API (`src/api/client.ts`)

Todas as URLs são relativas (`/api/...`), o que funciona em dev (proxy do Vite) e em produção (Nginx no mesmo domínio, sem CORS).

Os tipos do contrato ficam em `src/api/types.ts` e espelham a seção 5 do PRD: `PersonaId`, `ChatMessage` (`role`, `content`, `created_at`), `SessionCreated`, `SessionDetail`, `SendMessageResponse` e `ApiErrorBody`. As funções do cliente devolvem `Promise` desses tipos, e a resposta do `fetch` é validada com um type guard antes de ser usada, sem `as` solto nem `any`.

| Função | Requisição | Retorno em sucesso |
|---|---|---|
| `createSession(persona)` | `POST /api/sessions` `{ persona }` | `{ session_id, persona, created_at }` |
| `getSession(id)` | `GET /api/sessions/{id}` | `{ session_id, persona, created_at, last_activity, messages }` |
| `sendMessage(id, content)` | `POST /api/sessions/{id}/messages` `{ content }` | `{ session_id, reply }` |
| `deleteSession(id)` | `DELETE /api/sessions/{id}` | nada (204) |

### Normalização de erros

Toda falha vira um `ApiError` com `{ status, code, message }`, para os componentes nunca lidarem com `fetch` cru:

| Situação | `status` | `code` | `message` exibida |
|---|---|---|---|
| Resposta com corpo no formato `{ error: { code, message } }` | status HTTP | `error.code` | `error.message` da API |
| `fetch` lança exceção (rede, DNS, CORS) | `0` | `network_error` | "Não foi possível falar com o servidor. Tente novamente." |
| Corpo não é JSON (ex.: 502 em HTML do Nginx) | status HTTP | `network_error` | "Não foi possível falar com o servidor. Tente novamente." |

- `deleteSession` ignora 404 (a sessão já pode ter expirado).
- Nada de timeout no cliente: o backend responde em até 60 s (`LLM_TOTAL_TIMEOUT_S`) e o Nginx corta em 90 s.

---

## 5. Estado e fluxos

### 5.1 Estado (`useReducer` em `App.tsx`)

```js
{
  screen: "start" | "loading" | "chat",
  session: { id, persona } | null,
  messages: [{ localId, role, content, created_at, status: "ok" | "pending" | "error", error }],
  waiting: false,
  notice: null
}
```

- `localId` é gerado no cliente (`crypto.randomUUID()`) só para a `key` do React e para achar a mensagem que falhou.
- `notice` guarda avisos de tela, como "Sua sessão expirou".

### 5.2 Ao abrir a página

1. Lê `sessionStorage["chat.session_id"]`.
2. Sem ID: mostra `StartScreen`.
3. Com ID: `screen = "loading"`, chama `getSession(id)`.
   - 200: preenche `messages` e vai para o chat.
   - 404: apaga o ID, volta para `StartScreen` com `notice = "Sua sessão expirou"`.
   - Erro de rede: mostra a mensagem genérica com botão "Tentar de novo", que repete o `getSession`.

### 5.3 Iniciar conversa

1. Usuário escolhe "Assistente geral" (`geral`) ou "Orientação jurídica" (`juridico`) e clica em "Iniciar conversa".
2. `createSession(persona)`; botão desabilitado durante a chamada.
3. Salva `session_id` no `sessionStorage` e abre o chat vazio com o `SessionBadge`.

### 5.4 Enviar pergunta

1. Texto com `trim()` vazio não envia. Mais de `MAX_CHARS` (2000) também não.
2. A mensagem do usuário entra na lista na hora com `status: "pending"`, o input é limpo e desabilitado, e aparece "digitando…".
3. `sendMessage(id, content)`:
   - 200: mensagem do usuário vira `ok` e a resposta entra na lista.
   - 404: fluxo de sessão expirada (igual 5.2).
   - 422, 503, 504, 500 ou rede: mensagem do usuário vira `error` com a `message` da API e o botão "Tentar de novo", que reenvia o mesmo texto.
4. Input volta a ser habilitado e recebe o foco.

### 5.5 Nova conversa

1. `deleteSession(id)` ignorando 404.
2. Apaga o ID do `sessionStorage`, zera o estado e volta para `StartScreen`.

---

## 6. Componentes

| Componente | Props | Responsabilidade |
|---|---|---|
| `StartScreen` | `notice`, `onStart(persona)`, `starting` | Escolha da persona em dois cartões selecionáveis, botão "Iniciar conversa", aviso de sessão expirada |
| `ChatWindow` | `session`, `messages`, `waiting`, `onSend`, `onRetry`, `onNewChat` | Layout em coluna: cabeçalho (badge + "Nova conversa"), lista e input |
| `SessionBadge` | `sessionId`, `persona` | Mostra os 8 primeiros caracteres do ID e a persona; clique copia o ID completo com `navigator.clipboard` e mostra "Copiado" por 2 s |
| `MessageList` | `messages`, `waiting`, `onRetry` | Rolagem automática para a última mensagem a cada mudança; indicador "digitando…" no fim |
| `MessageBubble` | `message`, `onRetry` | Usuário: texto puro com `whitespace-pre-wrap`, alinhado à direita. Assistente: `react-markdown`, alinhado à esquerda. Estado de erro com texto e botão "Tentar de novo" |
| `MessageInput` | `disabled`, `onSend` | Textarea; Enter envia, Shift+Enter quebra linha; contador `n/2000` que fica vermelho perto do limite; botão Enviar |

Regras gerais:

- `useEffect` só onde não tem alternativa: carga inicial do histórico e rolagem da lista.
- Sem comentários no código; nomes claros fazem esse papel.
- Textos da interface em português do Brasil.
- Acessibilidade básica: `label` no textarea, `aria-live="polite"` na lista de mensagens, botões com texto visível, foco visível no teclado.

---

## 7. Layout e responsivo

- Tela cheia em coluna: cabeçalho fixo no topo, lista com rolagem no meio, input fixo embaixo.
- Largura máxima do conteúdo em `max-w-3xl`, centralizado no desktop.
- Em 360px: balões com até 85% da largura, badge e "Nova conversa" cabem em uma linha, textarea com no máximo 5 linhas.
- Altura com `h-dvh` para o teclado do celular não esconder o input.
- Testar em 360px, 390px e 1280px.

---

## 8. Testes (PRD 8.6)

Vitest + Testing Library, com `fetch` mockado por `vi.fn()` em cada teste.

| Arquivo | Caso | Resultado esperado |
|---|---|---|
| `client.test.ts` | API devolve `{ error: { code, message } }` | `ApiError` com o `code` e a `message` da API |
| `client.test.ts` | `fetch` lança exceção | `ApiError` com `network_error` e mensagem genérica |
| `client.test.ts` | 502 com corpo HTML | `ApiError` com `network_error` |
| `startSession.test.tsx` | Criar sessão | ID salvo no `sessionStorage` e `SessionBadge` com os 8 primeiros caracteres |
| `sendMessage.test.tsx` | Enviar mensagem | Resposta renderizada; input desabilitado enquanto aguarda |
| `sendMessage.test.tsx` | Enter e Shift+Enter | Enter envia; Shift+Enter não envia |
| `markdown.test.tsx` | Resposta com `**x**` | Renderiza `<strong>x</strong>` |
| `markdown.test.tsx` | Resposta com `<script>` | Aparece como texto e nenhum `<script>` entra no DOM |
| `errors.test.tsx` | 404 ao recarregar | Volta para `StartScreen` com "Sua sessão expirou" |
| `errors.test.tsx` | 503 ao enviar | Mostra a mensagem da API e "Tentar de novo"; o clique reenvia o mesmo texto |
| `errors.test.tsx` | Exceção de rede ao enviar | Mostra "Não foi possível falar com o servidor. Tente novamente." |

Comando: `npm test` (roda `vitest run`). Os testes, o `npm run typecheck` e o `npm run lint` precisam passar antes de abrir cada PR.

---

## 9. Plano de execução

Branches no padrão `feat/frontend-<descricao>`, um PR por fase, revisado pelo Eduardo. Commits seguindo o [AGENTS.md](../AGENTS.md).

### Fase 0. Repositório e organização (entrega transversal) · seg 09/11 · #1

- [x] Criar o repositório `comp-aplicada/chatbot-multiusuario-tca`
- [x] Subir enunciado, PRD e `AGENTS.md`
- [x] Criar as pastas `backend/`, `frontend/`, `infra/`, `scripts/` e `docs/`
- [x] Adicionar `.gitignore` com `.env` desde o início
- [x] Convidar Pedro, Maria Eduarda e Eduardo como colaboradores com permissão de escrita. Todos com acesso de escrita e a Maria Eduarda (`DudaGomes`) já associada às issues dela
- [x] Criar o board de tasks (GitHub Projects) com uma task por célula de "Módulo", "Testes" e "Entrega transversal" da tabela 9 do PRD, com datas de início e entrega e a milestone "Apresentação (26/11)"
- [x] Criar `.github/pull_request_template.md` (o que mudou, como testar, checklist de testes)
- [x] Ativar proteção da `main`: PR obrigatório com 1 aprovação, sem push direto, valendo também para admins
- [ ] Mandar no grupo o link do repo e do board

### Fase 1. Esqueleto · ter 10/11 · `feat/frontend-setup` · #4

- [x] `npm create vite@latest frontend -- --template react`
- [x] Instalar Tailwind v4, `react-markdown`, Vitest, Testing Library e jsdom
- [x] `vite.config.ts` com proxy `/api` para `http://localhost:8000` e bloco `test` (jsdom, `tests/setup.ts`)
- [x] `constants.ts` com `MAX_CHARS = 2000`, personas e textos fixos
- [x] Scripts `dev`, `build` (`tsc -b && vite build`), `preview`, `test`, `typecheck`, `lint` no `package.json`
- [x] Projeto em TypeScript: `tsconfig` com `strict`, testes incluídos no typecheck e `any` proibido no lint
- [x] `npm run build` gera `dist/` sem erro (o Pedro depende disso no `web.Dockerfile`)
- [ ] Abrir o PR da branch `feat/frontend-setup` para a `main`, com revisão do Eduardo

### Fase 2. Cliente da API e estado · qua 11/11 · `feat/frontend-api-client` · #5

- [ ] `types.ts` com os tipos do contrato da API
- [ ] `client.ts` com as 4 funções tipadas e o `ApiError`
- [ ] `chatReducer.ts` com as ações `start`, `loaded`, `send`, `reply`, `fail`, `retry`, `expired`, `reset`
- [ ] Testes de `client.test.ts`
- [ ] Rodar contra o stub da API da Maria Eduarda (`uvicorn` local) e conferir o formato das respostas

### Fase 3. Telas · sex 13/11 · `feat/frontend-chat` · #13

- [ ] `StartScreen` com escolha de persona
- [ ] `ChatWindow`, `SessionBadge`, `MessageList`, `MessageBubble`, `MessageInput`
- [ ] Persistência do ID em `sessionStorage` e recarga do histórico no F5
- [ ] Botão "Nova conversa"
- [ ] Layout responsivo validado em 360px no DevTools

### Fase 4. Erros e testes · seg 16/11 · `feat/frontend-erros` · #15 e #16

- [ ] Fluxo de sessão expirada (404 no load e no envio)
- [ ] Mensagem com erro e "Tentar de novo" para 422, 503, 504, 500 e rede
- [ ] Todos os testes da seção 8 passando
- [ ] Seção "Front-end: como rodar" no README

### Fase 5. Integração com produção · qua 18/11 · #21

- [ ] Front servido pelo Nginx da EC2 junto com o Pedro (`infra/web.Dockerfile`)
- [ ] Conversa completa em `https://<domínio>` com o LLM real
- [ ] Três abas com personas diferentes conversando ao mesmo tempo

### Fase 6. Ensaio e congelamento · ter 24/11 e qua 25/11 · #29 e #30

- [ ] Checklist manual da seção 10 contra produção
- [ ] Teste da versão local (`docker compose -f docker-compose.yml -f docker-compose.local.yml up --build`) no notebook da apresentação
- [ ] Gerar o QR code de `https://<domínio>` para o slide da demo
- [ ] Gravar vídeo de backup da demo
- [ ] Ensaiar os blocos de 12 a 17 min e de 22 a 26 min
- [ ] Congelamento do código na terça 24/11 às 18h

### Apresentação · qui 26/11 · #31

- [ ] Bloco "Front-end React e fluxo de sessão no navegador" (12 a 17 min)
- [ ] Conduzir a demo ao vivo (22 a 26 min)

---

## 10. Checklist manual (PRD 8.7, contra produção)

- [ ] F5 mantém o histórico
- [ ] Duas abas mostram IDs diferentes
- [ ] Clicar no badge copia o ID completo
- [ ] "Nova conversa" volta para a `StartScreen` e a sessão antiga some do servidor
- [ ] Enter envia e Shift+Enter quebra linha
- [ ] Contador não deixa passar de 2000 caracteres
- [ ] Resposta com Markdown (lista, negrito, código) renderiza bem
- [ ] Layout funciona em 360px no DevTools e em um celular real
- [ ] Com `SESSION_TTL_MIN=1` rodando localmente, a sessão expira e aparece "Sua sessão expirou"
- [ ] Com o container `api` parado, aparece a mensagem genérica e "Tentar de novo" funciona depois que ele volta

---

## 11. Roteiro da apresentação (minha parte)

### Bloco 12 a 17 min: front-end

1. Por que React + Vite + TypeScript: componentes pequenos, estado da conversa num único reducer e o contrato da API checado na compilação.
2. Fluxo da sessão no navegador: `POST /api/sessions` gera o UUID no servidor, o front guarda em `sessionStorage`, cada aba é um usuário.
3. F5 recarrega o histórico com `GET /api/sessions/{id}`; 404 leva a "Sua sessão expirou".
4. Segurança: Markdown sem `rehype-raw`, então HTML do modelo não executa.
5. `client.ts` como único ponto de rede e o tratamento de erros padronizado.

### Bloco 22 a 26 min: demo

1. Abrir 3 abas: duas com "Assistente geral" e uma com "Orientação jurídica"; mostrar os IDs diferentes no badge.
2. Em cada aba, dizer um nome diferente e depois perguntar "Qual é o meu nome?" para provar o isolamento.
3. Mostrar o QR code para a turma entrar.
4. Passar para o Eduardo rodar o `concurrency_test.py` e para o Pedro mostrar os logs.

---

## 12. Dependências e riscos

| Dependência ou risco | De quem | Plano B |
|---|---|---|
| Stub da API com o formato do contrato | Maria Eduarda | Desenvolver com `fetch` mockado nos testes e um JSON fixo até o stub chegar |
| `infra/web.Dockerfile` e Nginx servindo o `dist/` | Pedro | Garantir que `npm ci && npm run build` funciona limpo em Node 20 |
| Domínio e HTTPS no ar | Pedro | Demo pela versão local em `http://localhost:8080` |
| `MAX_CHARS` diferente de `MESSAGE_MAX_CHARS` | Eu e Maria Eduarda | Conferir o `.env.example` antes do congelamento |
| `navigator.clipboard` exige HTTPS | Eu | Em HTTP local, o badge mostra o ID completo num `title` em vez de copiar |
