# Achados e aprendizados

Registro dos problemas, descobertas e decisões que surgiram durante o desenvolvimento, com os números medidos. Serve de material de estudo para a apresentação de 26/11: cada achado traz o que aconteceu, como foi descoberto, o que foi feito e como explicar.

Quando aparecer um achado novo, ele entra aqui, no tópico certo, com data, números e link para o PR ou a issue.

## Resumo para a apresentação

| # | Achado | Impacto | O que fizemos |
|---|---|---|---|
| 1 | O Groq desligou o `qwen3-32b` | O modelo do PRD não existia mais no provedor gratuito | Desenvolvimento passou para o `qwen3.8-27b` |
| 2 | O Groq desconta o limite de tokens por uma estimativa que cresce com o `max_tokens` | O limite real é menor do que parece | Medimos com 5 e 10 usuários |
| 3 | O Groq gratuito tem um limite oculto de 1.000 tokens de saída por minuto | 429 depois de 2 ou 3 respostas longas | Demo na DeepInfra; documentado no README |
| 4 | O Qwen3-32B na DeepInfra gera só 27 tokens/s | Respostas longas passavam de 38 s e estouravam o timeout de 20 s | Limite de palavras nos prompts |
| 5 | O modelo inventa leis e artigos | Resposta jurídica errada com aparência de certa | Persona jurídica cita só o nome da norma |
| 6 | Comparação de 6 modelos Qwen3 | Qwen3-32B ficou atrás em qualidade e velocidade | Demo trocada para o `Qwen3.8-27B` na DeepInfra |
| 7 | O Qwen3.8 ignora o `/no_think` na DeepInfra | Respostas cortadas, só 21 palavras | `reasoning_effort: none` no `LLM_EXTRA_BODY` |
| 8 | Respostas da DeepInfra começam com linhas em branco | Nenhum, já tratado | O `strip()` do `LLMClient` resolve |
| 9 | O `openai` 3.x troca o `httpx` pelo `httpx2` | Os testes com `respx` acessavam a rede de verdade | Versão travada em `openai<3` |
| 10 | 10 usuários em paralelo levam o mesmo tempo que 1 (teste direto no `LLMClient`) | O cliente faz as chamadas em paralelo sem misturar históricos | A prova contra o servidor vem do pytest (#17) e do `concurrency_test.py` (#22) |
| 11 | Número de tentativas do LLM para o log, sem mudar a interface | A rota precisa logar `attempts=` | `ContextVar` isolado por requisição |
| 12 | O padrão do `LLM_EXTRA_BODY` no PRD era `{}` | Um `.env` de produção sem essa linha faria a DeepInfra cortar as respostas | Padrão passa a ser `{"reasoning_effort":"none"}` |
| 13 | Apagar a branch base fecha o PR empilhado | O #38 foi fechado sozinho no merge do #37 | PR reaberto como #42; evitar PRs empilhados |
| 14 | Vitest 5 e jsdom 31 não rodam no Node 20 | O build passava, mas nenhum teste do front rodava no `node:20` do Dockerfile | `engines.node` em Node 22+ e `node:22` no `web.Dockerfile` |
| 15 | Resposta atrasada da conversa antiga derrubava a conversa nova | "Nova conversa" no meio de uma pergunta jogava o usuário para "Sua sessão expirou" | O front ignora respostas de uma sessão que não é mais a da aba |
| 16 | Reiniciar o container `api` apaga todas as sessões | Quem estiver conversando cai em "Sua sessão expirou" | Não fazer deploy durante a demo |
| 17 | HTML do modelo na resposta | Um `<script>` na resposta poderia executar no navegador | `react-markdown` sem `rehype-raw` mostra o HTML como texto, com teste |

---

## LLM e provedores

### 1. O Groq desligou o Qwen3-32B (09/11)

- **O que aconteceu:** o PRD previa o `qwen/qwen3-32b` no Groq, mas o Groq desligou esse modelo em 17/07/2026 ([deprecações](https://console.groq.com/docs/deprecations)). O único Qwen que sobrou no Groq é o `qwen/qwen3.8-27b`, ainda em *preview*.
- **O que fizemos:** o desenvolvimento passou a usar o `qwen/qwen3.8-27b`, com `LLM_EXTRA_BODY={"reasoning_effort":"none"}` para desligar o raciocínio (PR #36).
- **Para explicar:** como o cliente usa a API compatível com a OpenAI e lê modelo, URL e parâmetros só do `.env`, a troca não mexeu em nenhuma linha de código.

### 2. Como o Groq conta o limite de tokens por minuto (14/11)

- **Limites do plano gratuito para o `qwen3.8-27b`**, conferidos no painel: 30 requisições por minuto, 1.000 por dia, 8.000 tokens por minuto e 200.000 tokens por dia.
- **Descoberta:** o Groq desconta do limite uma estimativa feita na hora da chamada, não o uso real. Com `max_tokens=1024`, uma chamada que usou 30 tokens descontou cerca de 363 do limite. Isso aparece no header `x-ratelimit-remaining-tokens`.
- **Medição** com o teste de concorrência (2 mensagens por usuário, todos em paralelo):

  | Usuários | Requisições | Respostas certas | 429 |
  |---|---|---|---|
  | 10 | 20 | 19 | 1 |
  | 5 | 10 | 10 | 0 |

- **Decisão:** `--users 5` no Groq e `--users 10` só na DeepInfra (README).

### 3. Limite oculto de tokens de saída no Groq (14/11)

- **O que aconteceu:** testando as personas, uma resposta trabalhista longa e as chamadas seguintes falharam com 429, mesmo com os retries.
- **Descoberta:** o erro dizia "output tokens per minute (OTPM): Limit 1000". Esse limite **não aparece em Settings > Limits**. Cada chamada reserva de 440 a 512 tokens dele antes de responder, então duas ou três respostas longas seguidas já estouram.
- **Detalhe:** nesse 429, o Groq manda `retry-after` de 8 a 12 s, e o nosso retry espera só 1 s e depois 2 s (regra do PRD). Por isso o retry não salva esse caso, e o usuário vê "modelo indisponível".
- **O que fizemos:** nada no código, porque a demo roda na DeepInfra, que não tem esse limite. O limite ficou documentado no README e no PR #38.
- **Para explicar:** é a justificativa concreta para usar um provedor pago na demo. Com a turma inteira, o plano gratuito não aguenta.

### 4. O Qwen3-32B na DeepInfra é lento demais para respostas longas (14/11)

- **O que aconteceu:** a pergunta "Fui demitido sem justa causa. Quais verbas eu recebo?" deu `LLMTimeout`.
- **Medição:** o Qwen3-32B na DeepInfra gera cerca de **27 tokens/s**. A resposta tinha cerca de 1.000 tokens e levou 37,6 s, quase o dobro do `LLM_TIMEOUT_S` de 20 s. Em 20 s, cabem uns 500 tokens.
- **O que fizemos:** limite de 200 palavras na persona `geral` e de 250 na `juridico`, "a não ser que o usuário peça mais detalhes" (PR #37). Com o limite, as respostas jurídicas ficaram entre 7 e 17 s.
- **Para explicar:** é um exemplo de como o tratamento de erro funcionou. O timeout virou o 504 previsto no contrato em vez de travar a requisição.

### 5. O modelo inventa leis (14/11)

- **O que aconteceu:** mesmo com "cite a lei quando souber com segurança" no prompt, o Qwen3-32B citou um "art. 53-B do CDC" e uma "Lei 12.425/2011 (Lei do Sossego)", que não existem. Também inventou um prazo de 30 dias para o reembolso no direito de arrependimento.
- **O que fizemos:** a persona jurídica agora não cita números de artigos nem de leis, só o nome da norma (CLT, Código de Defesa do Consumidor, Código Civil), e diz quando é preciso confirmar uma regra (PR #37).
- **Limite:** isso tira os números falsos, mas não impede o modelo de errar o conteúdo. Por isso a persona sempre lembra que não substitui um advogado.
- **Para explicar:** LLMs geram texto plausível, não consultam a lei. Citação inventada é o tipo de erro mais perigoso, porque parece confiável.

### 6. Comparação de modelos e troca do modelo da demo (14/11)

- **Método:** 10 perguntas fixas (conhecimento geral, técnica, raciocínio, 2 jurídicas e continuidade de contexto), com os prompts reais, em 6 modelos Qwen3 ([escolha do modelo](escolha-do-modelo.md), PR #40).
- **Resultado:**

  | Modelo | Provedor | Média | Máxima | Nota proposta |
  |---|---|---|---|---|
  | Qwen3-32B | DeepInfra | 5,4 s | 12,1 s | 3 |
  | Qwen3-14B | DeepInfra | 4,8 s | 16,6 s | 4 |
  | Qwen3-30B-A3B | DeepInfra | 2,2 s | 4,0 s | 3 |
  | Qwen3-235B-A22B-Instruct-2507 | DeepInfra | 6,9 s | 20,7 s | 4 |
  | **Qwen3.8-27B** | DeepInfra | **2,6 s** | **6,3 s** | **5** |
  | qwen3.8-27b | Groq | 0,8 s | 1,1 s | 4 |

- **Decisão:** a demo usa o `Qwen/Qwen3.8-27B` na DeepInfra (PR #36). É o mesmo modelo do desenvolvimento no Groq, 2× mais rápido que o Qwen3-32B e o mais correto nas perguntas jurídicas.
- **Custo:** cerca de US$ 0,00026 por pergunta. Os US$ 5 de crédito pagam perto de 19 mil perguntas.
- **Para explicar:** modelo maior não é sempre melhor. O 235B foi o mais completo na pergunta trabalhista, mas passou do timeout. O 30B-A3B (MoE) foi rápido, mas inventou mais.

### 7. O Qwen3.8 ignora o `/no_think` na DeepInfra (14/11)

- **O que aconteceu:** na primeira rodada da comparação, o Qwen3.8-27B na DeepInfra custou 12× mais que os outros.
- **Descoberta:** sem `reasoning_effort: "none"`, ele raciocina escondido, num campo `reasoning_content` que não chega ao usuário. Na pergunta trabalhista, gastou os 1.024 tokens pensando, levou 16 s e devolveu só 21 palavras de resposta. Com o parâmetro, levou 6 s e entregou 209 palavras.
- **O que fizemos:** `LLM_EXTRA_BODY={"reasoning_effort":"none"}` também no bloco da DeepInfra do `.env.example`.
- **Para explicar:** o `/no_think` no prompt é um *soft switch* dos Qwen3 originais. O Qwen3.8 precisa do parâmetro da API, e a limpeza do `<think>` no `LLMClient` continua como garantia.

### 8. Respostas da DeepInfra começam com linhas em branco (14/11)

- Algumas respostas chegam como `"\n\nOi!"`, provavelmente sobra de um bloco de raciocínio vazio removido pelo provedor. O `strip()` do `LLMClient` já resolve.

---

## Testes

### 9. O `openai` 3.x quebra os testes com `respx` (09/11)

- **O que aconteceu:** com o SDK `openai` 3.x, os testes do `LLMClient` tentavam acessar a rede de verdade.
- **Descoberta:** o 3.x trocou o `httpx` pelo `httpx2`, e o `respx` só intercepta o `httpx`.
- **O que fizemos:** `openai>=2.54,<3` no `requirements.txt`. O 2.54 tem a mesma API usada (`AsyncOpenAI`, `extra_body`, as exceções). São 31 testes, todos passando (PR #38).

---

## Concorrência

### 10. 10 usuários em paralelo levam o mesmo tempo que 1 (14/11)

- **Medição:** com o `LLMClient` e o `Qwen3.8-27B` na DeepInfra, 10 usuários enviaram em paralelo "Meu nome é <Nome>" e depois "Qual é o meu nome?". O resultado foi 10/10 respostas certas, sem nenhum nome trocado, em 2,8 s no total, com cada segunda resposta entre 0,3 e 0,8 s.
- **Para explicar:** se as chamadas fossem feitas uma por vez, o total seria perto da soma das latências. O total perto da latência de um usuário mostra que as chamadas ao LLM rodam em paralelo (asyncio) e que cada histórico fica separado. **Esse teste foi direto no `LLMClient`, sem a API**: ele mostra o comportamento do cliente e do provedor, não do servidor. A prova de que o servidor não serializa e não mistura sessões vem do teste determinístico do pytest (#17) e do `scripts/concurrency_test.py` contra produção (#22).

### 11. Número de tentativas por requisição com `ContextVar` (14/11)

- **O problema:** o log de cada mensagem (PRD 5.7) tem `attempts=`, mas o `chat(...)` do `LLMClient` só devolve o texto. Mudar a assinatura quebraria o contrato combinado com a rota (#14).
- **O que fizemos:** um `ContextVar` (`llm_attempts`) que o `chat` atualiza a cada tentativa. A rota lê o valor depois do `await`, com sucesso ou erro (PR #42, sugestão da Maria Eduarda na revisão).
- **Por que não uma variável global:** o servidor atende várias requisições ao mesmo tempo no mesmo processo. Uma global seria sobrescrita por outra requisição no meio do caminho. Com o `ContextVar`, cada requisição roda na sua própria task do asyncio, com uma cópia do contexto, e não vê o valor das outras. Há um teste com duas chamadas concorrentes, uma com retry e outra sem, que confirma 2 e 1 tentativas.
- **Para explicar:** é a versão asyncio da "variável por thread" (thread-local). Mostra que a concorrência foi pensada também nos detalhes, não só nas sessões.

---

## Configuração

### 12. O padrão do `LLM_EXTRA_BODY` no PRD era `{}` (14/11)

- **O risco:** a tabela 7.1 do PRD dava `{}` como padrão do `LLM_EXTRA_BODY`, e o `config.py` (#6) ia seguir a tabela. Se o `.env` de produção esquecesse essa linha, a DeepInfra voltaria a raciocinar escondido e a devolver respostas cortadas (achado 7).
- **Como apareceu:** na revisão do #36, a Maria Eduarda avisou que ia usar `{}` como padrão, seguindo o PRD.
- **O que fizemos:** o padrão no PRD passa a ser `{"reasoning_effort":"none"}`, que vale para os dois provedores (PR #43). Assim, o caso seguro é o padrão.
- **Para explicar:** configuração padrão deve ser a segura. Errar o `.env` não pode quebrar a demo em silêncio.

---

## Processo

### 13. Apagar a branch base fecha o PR empilhado (14/11)

- **O que aconteceu:** o PR do `LLMClient` (#38) estava empilhado sobre o das personas (#37). No merge do #37, a opção de apagar a branch removeu a base do #38, e o GitHub fechou o #38 sozinho.
- **O que fizemos:** atualizamos a branch com a `main` e abrimos o #42 com a base na `main`, apontando para a revisão do #38.
- **Lição:** com `delete_branch_on_merge` ligado, o PR empilhado deve ter a base trocada para a `main` antes do merge do PR de baixo. Ou é melhor evitar PRs empilhados.

---

## Front-end

### 14. Vitest 5 e jsdom 31 não rodam no Node 20 (15/11)

- **O que aconteceu:** o `package.json` do front pedia Node `>=20.19`, a exigência do Vite 8. Na revisão do #35, o Eduardo rodou no `node:20`, a imagem prevista para o build do `web.Dockerfile`: o `npm run build` passou, mas o Vitest não rodou nenhum teste (`Failed to start forks worker`).
- **Descoberta:** as dependências de teste travadas no lockfile pedem mais que o Vite: `vitest` 5.1 pede `^22.12`, `jsdom` 31 pede `^22.22.2 || ^24.15 || >=26` e o `undici` pede `>=22.19`.
- **O que fizemos:** `engines.node` passou para `^22.22.2 || ^24.15.0 || >=26`, o PRD e o plano apontam `node:22` no `web.Dockerfile`, e os testes foram rodados no Node 22.22.2 e no 26 (PR #35).
- **Para explicar:** "o build passa" não garante que os testes rodam. A versão mínima do runtime vem da dependência mais exigente, não da ferramenta principal.

### 15. Resposta atrasada da conversa antiga derrubava a conversa nova (15/11)

- **O cenário:** o usuário manda uma pergunta e, antes da resposta, clica em "Nova conversa". O front chama `DELETE` na sessão, e o backend faz a pergunta em andamento terminar em 404 (teste de concorrência do #17). Se o usuário já tiver começado outra conversa, esse 404 atrasado levava ao fluxo de sessão expirada, que apagava o ID novo e mostrava "Sua sessão expirou".
- **O que fizemos:** quando uma resposta chega, o front compara a sessão da pergunta com a que está salva no `sessionStorage` e descarta a resposta se não for mais a mesma. Um teste em `errors.test.tsx` reproduz o cenário e falha se essa checagem for removida.
- **Para explicar:** é o mesmo problema de concorrência do backend, só que no navegador: uma requisição assíncrona antiga não pode mexer no estado de quem já seguiu em frente.

### 16. Reiniciar o container `api` apaga todas as sessões (15/11)

- **O que aconteceu:** testando o front com a API local, derrubar a API mostrou a mensagem genérica com "Tentar de novo", como previsto. Ao subir a API de novo, o "Tentar de novo" levou para "Sua sessão expirou", porque as sessões vivem só na memória do processo.
- **Impacto na demo:** um deploy ou restart do container durante a apresentação desconecta toda a turma.
- **O que fizemos:** o front trata os dois casos sem quebrar a tela, e fica a regra de não fazer deploy durante a demo. Persistir sessões (Redis) está fora do escopo.

### 17. HTML vindo do modelo não executa (15/11)

- **O risco:** o modelo pode devolver HTML na resposta, por acidente ou por injeção no prompt, e um `<script>` ou um `<img onerror>` executaria no navegador de quem lê.
- **O que fizemos:** as respostas passam pelo `react-markdown` sem `rehype-raw`. O HTML aparece como texto e o Markdown (negrito, listas, código) continua funcionando. Os testes de `markdown.test.tsx` conferem que nenhum `<script>` nem `<img>` entra no DOM. As mensagens do usuário são texto puro.
- **Para explicar:** é a defesa contra XSS: o conteúdo do modelo é tratado como dado, nunca como código.

---

## Perguntas que o professor pode fazer

- **Por que Qwen3 e não GPT ou Gemini?** É open weight, bom em português e barato ou grátis via API compatível com a OpenAI. A comparação está nos achados 6 e 7.
- **Por que a comparação só tem modelos Qwen?** A família foi decidida antes, na seção 3 do PRD: open weight, boa em português, disponível nos dois provedores com API compatível com a OpenAI e de graça no Groq. A comparação escolheu o tamanho e a versão dentro dessa família, com o timeout de 20 s e o custo como restrições. Outras famílias (Llama, Mistral, DeepSeek) não foram testadas; o `scripts/compare_models.py` compara qualquer modelo da DeepInfra só mudando a lista `MODELS`.
- **Por que dois provedores?** O Groq é grátis e rápido para o desenvolvimento, mas o plano gratuito não aguenta a turma (achados 2 e 3). A DeepInfra é paga, sem esse limite, e a troca é só o `.env`.
- **O que acontece se o LLM demorar ou cair?** Timeout de 20 s por tentativa vira 504. 429, 5xx e erro de conexão têm até 2 novas tentativas (1 s e 2 s) e depois viram 503. Outros 4xx viram 503 sem retry. O achado 4 é um caso real de timeout.
- **O chatbot pode dar informação jurídica errada?** Pode (achado 5). Por isso a persona não cita artigos e sempre lembra que não substitui um advogado.
- **Como vocês provam que as conversas não se misturam?** Pelo teste de concorrência com nomes distintos (achado 10 e #22).
