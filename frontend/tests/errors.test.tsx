import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { MESSAGES, STORAGE_KEY } from '../src/constants.ts'
import {
  SESSION_ID,
  apiError,
  deferred,
  mockFetch,
  reply,
  requestOf,
  sessionCreated,
  sessionDetail,
} from './helpers.ts'

const NOT_FOUND = () => apiError(404, 'session_not_found', 'Sessão não encontrada ou expirada.')
const UNAVAILABLE = 'O modelo está indisponível no momento. Tente novamente.'

async function openChat(...responses: (Response | Promise<Response> | Error)[]) {
  sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
  const fetchMock = mockFetch(sessionDetail([]), ...responses)
  const user = userEvent.setup()
  render(<App />)
  const input = await screen.findByLabelText('Mensagem')
  return { fetchMock, user, input }
}

describe('erros e sessão expirada', () => {
  it('404 ao recarregar apaga o ID e volta para a tela inicial com "Sua sessão expirou"', async () => {
    sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
    mockFetch(NOT_FOUND())
    render(<App />)

    expect(await screen.findByText(MESSAGES.sessionExpired)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar conversa' })).toBeInTheDocument()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('404 durante o chat leva ao mesmo fluxo de sessão expirada', async () => {
    const { user, input } = await openChat(NOT_FOUND())

    await user.type(input, 'Oi{Enter}')

    expect(await screen.findByText(MESSAGES.sessionExpired)).toBeInTheDocument()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('503 ao enviar mostra a mensagem da API e "Tentar de novo" reenvia o mesmo texto', async () => {
    const { fetchMock, user, input } = await openChat(
      apiError(503, 'llm_unavailable', UNAVAILABLE),
      reply('Agora foi.'),
    )

    await user.type(input, 'Pergunta importante{Enter}')

    expect(await screen.findByText(UNAVAILABLE)).toBeInTheDocument()
    expect(input).toBeEnabled()

    await user.click(screen.getByRole('button', { name: MESSAGES.retry }))

    expect(await screen.findByText('Agora foi.')).toBeInTheDocument()
    expect(screen.queryByText(UNAVAILABLE)).not.toBeInTheDocument()
    expect(requestOf(fetchMock, 2).body).toEqual({ content: 'Pergunta importante' })
    expect(screen.getAllByText('Pergunta importante')).toHaveLength(1)
  })

  it.each([
    [422, 'invalid_request', 'Requisição inválida: content não pode ficar vazio.'],
    [504, 'llm_timeout', 'O modelo demorou demais para responder. Tente novamente.'],
    [500, 'internal_error', 'Erro interno do servidor.'],
  ])('%i ao enviar mostra a message da API com "Tentar de novo"', async (status, code, message) => {
    const { user, input } = await openChat(apiError(status, code, message))

    await user.type(input, 'Oi{Enter}')

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: MESSAGES.retry })).toBeInTheDocument()
  })

  it('exceção de rede ao enviar mostra a mensagem genérica', async () => {
    const { user, input } = await openChat(new TypeError('Failed to fetch'))

    await user.type(input, 'Oi{Enter}')

    expect(await screen.findByText(MESSAGES.networkError)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: MESSAGES.retry })).toBeInTheDocument()
  })

  it('502 em HTML do Nginx ao enviar mostra a mensagem genérica', async () => {
    const { user, input } = await openChat(new Response('<html>502 Bad Gateway</html>', { status: 502 }))

    await user.type(input, 'Oi{Enter}')

    expect(await screen.findByText(MESSAGES.networkError)).toBeInTheDocument()
  })

  it('erro de rede ao recarregar mostra "Tentar de novo", que repete o carregamento', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
    mockFetch(new TypeError('Failed to fetch'), sessionDetail([{ role: 'assistant', content: 'Voltei.' }]))
    render(<App />)

    await user.click(await screen.findByRole('button', { name: MESSAGES.retry }))

    expect(await screen.findByText('Voltei.')).toBeInTheDocument()
  })

  it('erro ao criar a sessão mostra a mensagem e libera o botão', async () => {
    const user = userEvent.setup()
    mockFetch(new TypeError('Failed to fetch'), sessionCreated())
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(MESSAGES.networkError)

    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))

    expect(await screen.findByText(SESSION_ID.slice(0, 8))).toBeInTheDocument()
  })

  it('resposta atrasada da conversa antiga não derruba a conversa nova', async () => {
    const oldAnswer = deferred<Response>()
    const newSessionId = '9b1d2c3e-0000-4000-8000-000000000000'
    const { user, input } = await openChat(oldAnswer.promise, new Response(null, { status: 204 }), sessionCreated('geral', newSessionId))

    await user.type(input, 'Pergunta lenta{Enter}')
    await user.click(screen.getByRole('button', { name: 'Nova conversa' }))
    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))
    await screen.findByText(newSessionId.slice(0, 8))

    oldAnswer.resolve(NOT_FOUND())

    await screen.findByLabelText('Mensagem')
    expect(screen.queryByText(MESSAGES.sessionExpired)).not.toBeInTheDocument()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe(newSessionId)
  })
})
