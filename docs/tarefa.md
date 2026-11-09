# Apresentação do Protótipo 1 (2ª Avaliação)

- **Data da apresentação:** 16/11/2026, presencial, em sala de aula
- **Duração:** 30 minutos por equipe
- **Entrega:** código-fonte publicado em repositório no GitHub

## Equipes

| Equipe | Integrantes |
|---|---|
| A | Francisco Rafael Meneses Gonçalves, Bernardo de Carvalho Cavalcante, Cauã Martins da Silva, Samara Feitosa de Sousa |
| **B** | **Pedro Feitosa Soares, Izaías de Melo Lima Morais, Maria Eduarda Farias Gomes, Eduardo Melo de Carvalho** |
| C | Anderson Felipe da Silva Pereira, Caio Victor Ferreira do Nascimento, Kauan Francisco Santos Saraiva, Rayanne Ellen Lopes Figueiredo |
| D | João Pedro Monteiro da Silva Barros, Lucas Herlon dos Santos Moreira Cunha, Otávio da Conceição França, Francielio Evangelista dos Santos Castro |

## Enunciado

Criar um chatbot simplificado em que vários usuários se conectam à aplicação e cada usuário faz perguntas genéricas ao chatbot. A aplicação responde a cada pergunta de cada usuário.

O controle de cada sessão pode ser feito por um **ID único gerado no instante em que o cliente HTTP se conecta** à aplicação servidora. O modelo LLM e a API de desenvolvimento são de livre escolha.

## Requisitos funcionais

### RF1. Conexão multiusuário

- Permitir que vários usuários interajam com o chatbot simultaneamente.

### RF2. Gestão de sessões

- Identificar cada usuário no momento da conexão.
- Manter o histórico de conversa isolado para cada sessão.
- O histórico pode ser efêmero, ou seja, mantido apenas enquanto a sessão do usuário estiver ativa.

### RF3. Processamento de perguntas

- Responder perguntas genéricas usando um modelo LLM.
- Garantir que cada resposta seja entregue ao usuário correto.

## Requisitos de implementação

| Item | Regra |
|---|---|
| Modelo LLM | Livre: OpenAI GPT, Google Gemini ou modelos open weight / open source |
| Framework / API | Livre: LangChain, OpenAI SDK, Google Generative AI etc., ou Python puro |
| Backend | Qualquer stack (Python, Node.js, Java etc.) |
| Justificativa | A escolha do modelo e do framework deve ser justificada tecnicamente |

## Publicação e infraestrutura

| Item | Obrigatório | Observação |
|---|---|---|
| Implantação em AWS EC2 | Não | Vale **+1,0 ponto extra** |
| Acesso público | Sim | Endpoint público acessível pela internet |
| Documentação | Sim | Instruções de uso do endpoint (API) do backend |
| Repositório no GitHub | Sim | Código-fonte do protótipo publicado |

## Critérios de avaliação

1. Funcionamento correto do chatbot multiusuário.
2. Gestão adequada das sessões de cada usuário ativo.
3. Qualidade e coerência das respostas do LLM.
4. Implantação funcional na AWS EC2 (opcional, +1,0).
5. Acessibilidade pública da aplicação.
6. Organização e clareza do código.

## Observações importantes

- O controle de sessão por usuário é fundamental para diferenciar os usuários.
- A aplicação deve lidar com conexões concorrentes, permitindo acessos simultâneos de vários usuários.
- A escolha do modelo LLM e do framework é livre, mas precisa de justificativa técnica.
- O código-fonte deve estar publicado em um repositório do GitHub.

## Checklist de entrega

- [ ] Sessão com ID único gerado na conexão
- [ ] Histórico isolado por sessão
- [ ] Respostas do LLM entregues ao usuário correto
- [ ] Suporte a usuários simultâneos
- [ ] Endpoint público na internet
- [ ] Documentação de uso da API
- [ ] Justificativa técnica do modelo e do framework
- [ ] Deploy em AWS EC2 (extra)
- [x] Repositório no GitHub criado
- [ ] Apresentação de 30 minutos preparada
