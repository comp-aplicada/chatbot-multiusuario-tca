import { describe, expect, it } from 'vitest'
import { MESSAGES } from '../src/constants.ts'
import { chatReducer, initialState, startState, type ChatState } from '../src/state/chatReducer.ts'

const session = { id: '3f2a9c1e-8b7d-4c1a-9e2f-0a1b2c3d4e5f', persona: 'geral' as const }
const reply = { role: 'assistant' as const, content: 'Resposta', created_at: '2026-11-11T14:02:10Z' }

function chatWith(...actions: Parameters<typeof chatReducer>[1][]): ChatState {
  return actions.reduce(chatReducer, chatReducer(startState, { type: 'loaded', session, messages: [] }))
}

describe('chatReducer', () => {
  it('começa carregando quando já existe um ID salvo', () => {
    expect(initialState('abc').screen).toBe('loading')
    expect(initialState(null).screen).toBe('start')
  })

  it('abre o chat com o histórico do servidor', () => {
    const state = chatReducer(initialState('abc'), {
      type: 'loaded',
      session,
      messages: [reply],
    })

    expect(state.screen).toBe('chat')
    expect(state.session).toEqual(session)
    expect(state.messages).toMatchObject([{ content: 'Resposta', status: 'ok' }])
  })

  it('mostra a pergunta na hora como pendente e espera a resposta', () => {
    const state = chatWith({ type: 'send', localId: 'u1', content: 'Oi', createdAt: 'agora' })

    expect(state.waiting).toBe(true)
    expect(state.messages).toMatchObject([{ localId: 'u1', role: 'user', status: 'pending' }])
  })

  it('marca a pergunta como ok e adiciona a resposta', () => {
    const state = chatWith(
      { type: 'send', localId: 'u1', content: 'Oi', createdAt: 'agora' },
      { type: 'reply', localId: 'u1', reply, replyId: 'a1' },
    )

    expect(state.waiting).toBe(false)
    expect(state.messages).toMatchObject([
      { localId: 'u1', status: 'ok' },
      { localId: 'a1', role: 'assistant', content: 'Resposta' },
    ])
  })

  it('marca a pergunta com erro e libera o input', () => {
    const state = chatWith(
      { type: 'send', localId: 'u1', content: 'Oi', createdAt: 'agora' },
      { type: 'fail', localId: 'u1', error: 'O modelo está indisponível no momento. Tente novamente.' },
    )

    expect(state.waiting).toBe(false)
    expect(state.messages).toMatchObject([
      { status: 'error', error: 'O modelo está indisponível no momento. Tente novamente.' },
    ])
  })

  it('reenvia a pergunta com erro no fim da lista, como pendente', () => {
    const state = chatWith(
      { type: 'send', localId: 'u1', content: 'Primeira', createdAt: 'agora' },
      { type: 'fail', localId: 'u1', error: 'erro' },
      { type: 'send', localId: 'u2', content: 'Segunda', createdAt: 'agora' },
      { type: 'reply', localId: 'u2', reply, replyId: 'a2' },
      { type: 'retry', localId: 'u1' },
    )

    expect(state.waiting).toBe(true)
    expect(state.messages.map((message) => message.localId)).toEqual(['u2', 'a2', 'u1'])
    expect(state.messages.at(-1)).toMatchObject({ content: 'Primeira', status: 'pending', error: null })
  })

  it('ignora tentar de novo enquanto espera outra resposta', () => {
    const waiting = chatWith(
      { type: 'send', localId: 'u1', content: 'Primeira', createdAt: 'agora' },
      { type: 'fail', localId: 'u1', error: 'erro' },
      { type: 'send', localId: 'u2', content: 'Segunda', createdAt: 'agora' },
    )

    expect(chatReducer(waiting, { type: 'retry', localId: 'u1' })).toBe(waiting)
  })

  it('volta para a tela inicial com aviso quando a sessão expira', () => {
    const state = chatReducer(chatWith(), { type: 'expired' })

    expect(state).toEqual({ ...startState, notice: MESSAGES.sessionExpired })
  })

  it('nova conversa zera tudo', () => {
    const state = chatReducer(
      chatWith({ type: 'send', localId: 'u1', content: 'Oi', createdAt: 'agora' }),
      { type: 'reset' },
    )

    expect(state).toEqual(startState)
  })

  it('erro ao criar a sessão libera o botão e mostra a mensagem', () => {
    const state = chatReducer(chatReducer(startState, { type: 'start' }), {
      type: 'screenError',
      error: MESSAGES.networkError,
    })

    expect(state.starting).toBe(false)
    expect(state.error).toBe(MESSAGES.networkError)
  })
})
