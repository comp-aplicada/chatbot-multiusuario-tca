# Apresentação: front-end e demo (Izaías)

> Itens marcados com `[x]` já foram executados. Primeiro passo pendente: **gerar o QR code quando o Pedro confirmar o domínio** (#12) e colar os slides abaixo no arquivo único da apresentação (#29).

- **Blocos:** 12 a 17 min (front-end) e 22 a 26 min (demo ao vivo), seção 11 do PRD
- **Issue:** #31
- **Material de apoio:** [plano do front-end](plano-frontend.md), [achados](achados.md) 14 a 17, README "Front-end: como rodar"

## Checklist

- [x] Conteúdo dos slides do bloco do front (abaixo)
- [x] Roteiro da demo com as 3 abas, o teste do nome e o QR code (abaixo)
- [x] Falas de passagem para o Eduardo (script) e o Pedro (logs) (abaixo)
- [ ] Gerar o QR code de `https://<domínio>` (depende do domínio do Pedro, #12)
- [ ] Colar os slides no arquivo único da apresentação (#29)
- [ ] Combinar as passagens ao vivo com o Eduardo e o Pedro no ensaio (#29)
- [ ] Ensaiar os dois blocos dentro do tempo (#29)

---

## Bloco 12 a 17 min: front-end (5 slides, cerca de 1 min cada)

### Slide 1. Stack do front

- React 19 + Vite 8 + TypeScript em modo `strict`
- Tailwind para o layout responsivo, a partir de 360px
- Vitest + Testing Library: 49 testes, sem precisar da API

**Fala:** "O front é uma página React servida pelo mesmo Nginx da API. Usamos TypeScript porque o contrato da API vira tipo: se o backend mudar um campo, o front quebra na compilação, não na frente de vocês."

### Slide 2. Cada aba é um usuário

Diagrama sugerido:

```
Aba 1 ── POST /api/sessions ──> UUID 3f2a9c1e…  ──> sessionStorage da aba 1
Aba 2 ── POST /api/sessions ──> UUID 9b1d2c3e…  ──> sessionStorage da aba 2
```

- O UUID é gerado no servidor, o front só guarda
- `sessionStorage` é separado por aba e sobrevive ao F5
- O badge no topo mostra os 8 primeiros caracteres; o clique copia o ID completo

**Fala:** "Não tem login. O que separa um usuário do outro é o ID da sessão. Como o `sessionStorage` é por aba, cada aba vira um usuário diferente, e é isso que vocês vão ver na demo."

### Slide 3. F5 e sessão expirada

- F5: `GET /api/sessions/{id}` recarrega o histórico do servidor
- 404 (expirou, foi apagada ou a API reiniciou): apaga o ID e mostra "Sua sessão expirou"
- "Nova conversa": `DELETE` no servidor e volta para a tela inicial

**Fala:** "O histórico mora no servidor, não no navegador. O front só pede de novo. Se o servidor não conhece mais aquele ID, o usuário volta para o início com um aviso, em vez de uma tela quebrada."

### Slide 4. Erros sem tela quebrada

| Situação | O que o usuário vê |
|---|---|
| 503 ou 504 do LLM | A mensagem da API e "Tentar de novo", que reenvia o mesmo texto |
| API fora do ar ou 502 do Nginx | "Não foi possível falar com o servidor. Tente novamente." |
| "Nova conversa" no meio de uma resposta | A resposta atrasada da conversa antiga é descartada (achado 15) |

- `src/api/client.ts` é o único lugar com `fetch`; toda falha vira um `ApiError` com `status`, `code` e `message`

**Fala:** "Com a turma inteira usando ao mesmo tempo, vai ter rate limit e timeout. Cada erro da tabela do contrato tem um comportamento visível e recuperável, e todos têm teste."

### Slide 5. Markdown sem XSS

- As respostas do modelo usam Markdown: listas, negrito, código
- `react-markdown` sem `rehype-raw`: HTML vindo do modelo aparece como texto
- Teste: `<script>` e `<img onerror>` nunca entram no DOM

**Fala:** "O conteúdo do modelo é tratado como dado, nunca como código. Se alguém convencer o modelo a responder com um `<script>`, ele aparece na tela como texto."

**Passagem para o Pedro:** "Agora o Pedro mostra como isso tudo chega até vocês em HTTPS."

---

## Bloco 22 a 26 min: demo ao vivo (4 min)

### Antes de começar (no intervalo do bloco do Pedro)

- [ ] 3 abas abertas em `https://<domínio>`, na tela inicial, com zoom de 125% no navegador
- [ ] Terminal do Eduardo pronto com `python scripts/concurrency_test.py --base-url https://<domínio> --users 10`
- [ ] Terminal do Pedro pronto com os logs do container `api`
- [ ] Plano B aberto: versão local em `http://localhost:8080` e o vídeo de backup

### Roteiro

| Tempo | O que fazer | O que falar |
|---|---|---|
| 0:00 | Aba 1: "Assistente geral", Iniciar. Aba 2: "Assistente geral", Iniciar. Aba 3: "Orientação jurídica", Iniciar | "Três abas, três usuários. Olhem o ID no topo de cada uma: são diferentes." |
| 0:40 | Aba 1: "Meu nome é Aurélio. Guarde isso." Aba 2: "Meu nome é Benedita. Guarde isso." Aba 3: "Meu nome é Cassiano. Guarde isso." | "Cada usuário diz um nome diferente." |
| 1:20 | Nas 3 abas, rápido em sequência: "Qual é o meu nome? Responda só o nome." | "Agora as três perguntam ao mesmo tempo. Se as sessões se misturassem, alguém receberia o nome errado." |
| 2:00 | Mostrar as 3 respostas certas. Na aba 3, perguntar "Posso ser demitido por justa causa sem aviso?" | "E a aba 3 fala com outra persona, a jurídica, com outro prompt." |
| 2:30 | Mostrar o slide com o QR code | "Agora é com vocês: entrem pelo QR code e conversem. Cada celular é uma sessão." |
| 2:50 | Passar para o Eduardo | "Enquanto vocês usam, o Eduardo roda o teste com 10 usuários automáticos." |
| 3:30 | Passar para o Pedro | "E o Pedro mostra nos logs as sessões de vocês chegando, só com os 8 primeiros caracteres do ID." |

### Falas de passagem

- **Para o Eduardo:** "Eduardo, roda o teste de concorrência com 10 usuários contra produção." Ele explica a tabela: cada usuário recebeu o próprio nome, nenhum trocado.
- **Para o Pedro:** "Pedro, mostra os logs do container." Ele aponta `session_created`, `message` com a latência e o `attempts`, e que o ID completo nunca aparece.

### Se algo der errado

| Problema | O que fazer |
|---|---|
| Wi-Fi da sala caiu | Roteador do celular (#29); se não der, versão local em `http://localhost:8080` |
| O modelo respondeu 503 ou 504 | Clicar em "Tentar de novo" e aproveitar: "isso é o tratamento de erro que mostrei no slide 4" |
| Tudo fora do ar | Vídeo de backup da demo |
| A API reiniciou no meio da demo | As abas vão para "Sua sessão expirou" (achado 16); iniciar de novo e seguir |

---

## QR code

Quando o domínio estiver no ar, gere o QR code com:

```bash
npx --yes qrcode -o docs/qrcode-demo.png -w 800 https://<domínio>
```

Teste o QR code com dois celulares diferentes antes do ensaio.
