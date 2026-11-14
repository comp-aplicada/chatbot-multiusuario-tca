# Escolha do modelo

Comparação feita em 14/11/2026 para justificar o LLM do chatbot (seção 8.5 do PRD).

## Método

- **10 perguntas fixas em português**: 3 de conhecimento geral, 2 de explicação técnica, 2 de raciocínio simples, 2 jurídicas e 1 de continuidade de contexto.
- **Prompts reais do chatbot**: as perguntas jurídicas usam a persona `juridico` e as outras usam a `geral`, com o texto de `backend/app/llm/personas.py`.
- **Parâmetros do `.env.example`**: `temperature=0.7` e `max_tokens=1024`.
- **Continuidade de contexto**: o primeiro turno ("Meu nome é Epaminondas e eu moro em Teresina. Guarde isso.") entra no histórico, e só a resposta do segundo turno ("Qual é o meu nome e em que cidade eu moro?") é medida.
- **Latência**: tempo da requisição HTTP até a resposta completa, sem streaming, medido no notebook do Eduardo. Cada modelo respondeu às perguntas em sequência.
- **Execução**: cada pergunta rodou uma vez por modelo. Com uma amostra só, latências e notas servem para comparar ordens de grandeza, não diferenças pequenas.
- **Provedores**: DeepInfra, que é o provedor pago da demo, e Groq, que é o provedor gratuito do desenvolvimento. Todos os modelos são Qwen3, a família escolhida no PRD (open weight, bom em português).

As respostas completas, latências, tokens e custos estão em [`escolha-do-modelo-dados.json`](escolha-do-modelo-dados.json). Para repetir o teste:

```bash
DEEPINFRA_API_KEY=... GROQ_API_KEY=... python scripts/compare_models.py
```

## Resultados

| Modelo | Provedor | Latência média | Latência máxima | Tokens/s | Custo por pergunta | Nota (1 a 5) |
|---|---|---|---|---|---|---|
| `Qwen/Qwen3-32B` | DeepInfra | 5,4 s | 12,1 s | 26 | US$ 0,00005 | 3 |
| `Qwen/Qwen3-14B` | DeepInfra | 4,8 s | 16,6 s | 25 | US$ 0,00005 | 4 |
| `Qwen/Qwen3-30B-A3B` | DeepInfra | 2,2 s | 4,0 s | 51 | US$ 0,00007 | 3 |
| `Qwen/Qwen3-235B-A22B-Instruct-2507` | DeepInfra | 6,9 s | **20,7 s** | 22 | US$ 0,00010 | 4 |
| **`Qwen/Qwen3.8-27B`** | DeepInfra | **2,6 s** | **6,3 s** | 51 | US$ 0,00026 | **5** |
| `qwen/qwen3.8-27b` | Groq | 0,8 s | 1,1 s | 209 | grátis | 4 |

A nota é uma proposta do Eduardo, feita a partir da leitura das respostas, e **ainda precisa ser revisada pela equipe**. A latência máxima importa porque o `LLM_TIMEOUT_S` é de 20 s: uma resposta acima disso vira "O modelo demorou demais".

Em todos os modelos, as 5 perguntas objetivas (capital, autor e ano, contas, horário e continuidade de contexto) vieram certas, nenhuma resposta foi cortada pelo `max_tokens` e nenhuma trouxe `<think>`. O que separa os modelos são as perguntas jurídicas e a velocidade.

### Observações por modelo

- **Qwen3-32B (escolha original do PRD)**: lento, com 26 tokens/s. Na pergunta trabalhista, inventou verbas ("50% sobre o aviso prévio", "multa de 20% sobre o FGTS") e citou o Código Civil. Na de arrependimento, disse que o reembolso tem prazo de 30 dias, regra que não existe no CDC. Em testes anteriores, com o prompt sem limite de palavras, a resposta trabalhista levou 38 s e estourou o timeout.
- **Qwen3-14B**: respostas corretas, mas genéricas. Na pergunta trabalhista, lista "danos morais" como se fosse verba rescisória e levou 16,6 s, perto do limite.
- **Qwen3-30B-A3B (MoE)**: rápido, mas inventa. Citou uma "trilogia O Espírito Público" de Machado de Assis, que não existe, deu um prazo de reembolso de "10 dias úteis" e descreveu o FGTS como "8% do salário", sem a multa de 40%.
- **Qwen3-235B-A22B-Instruct-2507**: a resposta trabalhista mais completa (prazo de 10 dias para pagar, multa de 20% na rescisão por acordo), mas a mais lenta. Ela levou 20,7 s e passaria do timeout. Também inventou um prazo de 14 dias para o reembolso no CDC.
- **Qwen3.8-27B na DeepInfra**: as melhores respostas jurídicas do teste, com respostas diretas e todas abaixo de 7 s. Não inventou prazos nem verbas; os defeitos foram de redação, como "liberação de 40% sobre o saldo" do FGTS (o certo é multa de 40% mais o saque do saldo), dizer que o reembolso pode ser em crédito "conforme sua preferência" e um erro de digitação ("guarve"). **É preciso mandar `reasoning_effort: "none"`**: sem isso, o modelo ignora o `/no_think` e raciocina escondido. Num teste da pergunta trabalhista, ele gastou os 1.024 tokens pensando e devolveu só 21 palavras, em 16 s.
- **Qwen3.8-27B no Groq**: o mesmo modelo, cerca de 4 vezes mais rápido e de graça, mas com o limite de 1.000 tokens de saída por minuto do plano gratuito. Por isso, não aguenta a turma inteira na demo. Numa resposta, ele se corrigiu no meio do texto ("Não, cuidado: …"), e na trabalhista citou uma "carta de anuência", que não existe.

## Conclusão

O modelo recomendado para a demo é o **Qwen3.8-27B na DeepInfra** (`LLM_MODEL=Qwen/Qwen3.8-27B` com `LLM_EXTRA_BODY={"reasoning_effort":"none"}`). Ele é o mesmo modelo que já usamos no Groq durante o desenvolvimento, então o comportamento testado é o que a turma vai ver. Nas 10 perguntas, acertou todas as objetivas, deu as respostas jurídicas mais corretas e foi duas vezes mais rápido que o Qwen3-32B (média de 2,6 s contra 5,4 s), com folga grande sobre o timeout de 20 s. O custo, de cerca de US$ 0,00026 por pergunta, é cinco vezes o do Qwen3-32B, mas os US$ 5 de crédito pagam perto de 19 mil perguntas, muito mais do que a apresentação vai usar. O Qwen3-32B, escolha original do PRD, ficou atrás em qualidade jurídica e em velocidade. Os modelos maiores (235B) e menores (14B, 30B-A3B) também perderam: ou passam do timeout, ou inventam fatos com mais frequência. Seja qual for o modelo, ele continua inventando regras jurídicas de vez em quando, e por isso a persona jurídica sempre lembra que não substitui um advogado.
