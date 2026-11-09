# AGENTS.md

Instruções para agentes de código (Claude Code, Codex, Cursor etc.) que trabalham neste repositório.

## Documentos do projeto

- `docs/tarefa.md`: enunciado formalizado do trabalho (requisitos e critérios de avaliação).
- `docs/prd-chatbot-multiusuario.md`: PRD / spec técnica do chatbot da Equipe B.

## Commits

### Formato

```
<tipo>(<escopo>): <descrição>
```

- Commits 100% em português do Brasil: tipo em inglês padrão do Conventional Commits, escopo e descrição em português.
- Nunca misture idiomas no escopo ou na descrição.
- Descrição no imperativo, minúscula, sem ponto final, até 50 caracteres.
- Escopo curto, em português (termos técnicos comuns como `api`, `docker`, `readme` são aceitos).
- Quando houver detalhes, use corpo com bullets `- ` e mantenha o assunto curto.
- Nunca adicione `Co-Authored-By`, assinaturas ou qualquer menção de que o conteúdo foi gerado por IA.

### Tipos

`feat` | `fix` | `security` | `refactor` | `perf` | `style` | `docs` | `test` | `chore` | `build` | `ci` | `revert`

Para `security`, prefira o CWE como escopo quando fizer sentido (ex: `security(CWE-79): ...`).

### Fluxo

1. Antes de escrever a mensagem, rode `git log --oneline -15` e siga o padrão do histórico (tipo, escopo, uso de corpo).
2. Analise `git status` e `git diff HEAD` por inteiro e planeje todos os commits antes de executar.
3. Commite **todas** as mudanças do `git status`, separando em commits lógicos quando os assuntos forem diferentes.
4. Execute todos os `git add` + `git commit` encadeados com `&&` e termine com `git push`.

```bash
git add <arquivos1> && git commit -m "msg1" && git add <arquivos2> && git commit -m "msg2" && git push && git log --oneline -3
```

### Exemplos

```
feat(sessao): gerar uuid na conexão do cliente
fix(chat): entregar resposta para a sessão correta
docs(readme): adicionar exemplos de curl da api
chore(docker): adicionar compose para deploy na ec2
```

Com corpo:

```
feat(chat): manter histórico isolado por sessão

- Armazena mensagens em memória indexadas pelo id da sessão
- Envia o histórico da sessão como contexto para o llm
```
