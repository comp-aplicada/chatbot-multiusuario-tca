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
| 10 | 10 usuários em paralelo levam o mesmo tempo que 1 | Prova de que o servidor não serializa as chamadas ao LLM | Vira argumento da demo |

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
- **Para explicar:** se o servidor atendesse um usuário por vez, o total seria perto da soma das latências. O total perto da latência de um usuário mostra que as chamadas ao LLM rodam em paralelo (asyncio) e que o histórico de cada sessão fica isolado. Esse teste ainda foi direto no cliente; o oficial roda contra produção com o `scripts/concurrency_test.py` (#22).

---

## Perguntas que o professor pode fazer

- **Por que Qwen3 e não GPT ou Gemini?** É open weight, bom em português e barato ou grátis via API compatível com a OpenAI. A comparação está nos achados 6 e 7.
- **Por que dois provedores?** O Groq é grátis e rápido para o desenvolvimento, mas o plano gratuito não aguenta a turma (achados 2 e 3). A DeepInfra é paga, sem esse limite, e a troca é só o `.env`.
- **O que acontece se o LLM demorar ou cair?** Timeout de 20 s por tentativa vira 504. 429, 5xx e erro de conexão têm até 2 novas tentativas (1 s e 2 s) e depois viram 503. Outros 4xx viram 503 sem retry. O achado 4 é um caso real de timeout.
- **O chatbot pode dar informação jurídica errada?** Pode (achado 5). Por isso a persona não cita artigos e sempre lembra que não substitui um advogado.
- **Como vocês provam que as conversas não se misturam?** Pelo teste de concorrência com nomes distintos (achado 10 e #22).
