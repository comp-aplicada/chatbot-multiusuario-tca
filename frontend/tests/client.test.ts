import { describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  NETWORK_ERROR,
  createSession,
  deleteSession,
  getSession,
  sendMessage,
} from '../src/api/client.ts'
import { MESSAGES } from '../src/constants.ts'

const SESSION_ID = '3f2a9c1e-8b7d-4c1a-9e2f-0a1b2c3d4e5f'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

async function captureError(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) {
      return error
    }
    throw error
  }
  throw new Error('A promessa deveria ter falhado')
}

describe('client da API', () => {
  it('cria a sessão com a persona no corpo e URL relativa', async () => {
    const created = { session_id: SESSION_ID, persona: 'juridico', created_at: '2026-11-11T14:00:00Z' }
    const fetchMock = mockFetch(jsonResponse(201, created))

    await expect(createSession('juridico')).resolves.toEqual(created)

    expect(fetchMock).toHaveBeenCalledWith('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona: 'juridico' }),
    })
  })

  it('carrega o histórico da sessão', async () => {
    const detail = {
      session_id: SESSION_ID,
      persona: 'geral',
      created_at: '2026-11-11T14:00:00Z',
      last_activity: '2026-11-11T14:02:10Z',
      messages: [
        { role: 'user', content: 'Oi', created_at: '2026-11-11T14:02:05Z' },
        { role: 'assistant', content: 'Olá!', created_at: '2026-11-11T14:02:10Z' },
      ],
    }
    const fetchMock = mockFetch(jsonResponse(200, detail))

    await expect(getSession(SESSION_ID)).resolves.toEqual(detail)
    expect(fetchMock).toHaveBeenCalledWith(`/api/sessions/${SESSION_ID}`, undefined)
  })

  it('envia a pergunta e devolve a resposta do assistente', async () => {
    const reply = { role: 'assistant', content: 'Resposta', created_at: '2026-11-11T14:02:10Z' }
    const fetchMock = mockFetch(jsonResponse(200, { session_id: SESSION_ID, reply }))

    await expect(sendMessage(SESSION_ID, 'Pergunta')).resolves.toEqual({ session_id: SESSION_ID, reply })
    expect(fetchMock).toHaveBeenCalledWith(`/api/sessions/${SESSION_ID}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: 'Pergunta' }),
    })
  })

  it('transforma o formato de erro da API em ApiError com code e message', async () => {
    mockFetch(
      jsonResponse(503, {
        error: { code: 'llm_unavailable', message: 'O modelo está indisponível no momento. Tente novamente.' },
      }),
    )

    const error = await captureError(sendMessage(SESSION_ID, 'Pergunta'))

    expect(error.status).toBe(503)
    expect(error.code).toBe('llm_unavailable')
    expect(error.message).toBe('O modelo está indisponível no momento. Tente novamente.')
  })

  it('transforma exceção do fetch em network_error com a mensagem genérica', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    const error = await captureError(createSession('geral'))

    expect(error.status).toBe(0)
    expect(error.code).toBe(NETWORK_ERROR)
    expect(error.message).toBe(MESSAGES.networkError)
  })

  it('transforma 502 com corpo HTML do Nginx em network_error', async () => {
    mockFetch(new Response('<html><body>502 Bad Gateway</body></html>', { status: 502 }))

    const error = await captureError(sendMessage(SESSION_ID, 'Pergunta'))

    expect(error.status).toBe(502)
    expect(error.code).toBe(NETWORK_ERROR)
    expect(error.message).toBe(MESSAGES.networkError)
  })

  it('trata resposta 200 fora do contrato como network_error', async () => {
    mockFetch(jsonResponse(200, { session_id: SESSION_ID }))

    const error = await captureError(getSession(SESSION_ID))

    expect(error.code).toBe(NETWORK_ERROR)
  })

  it('ignora 404 ao apagar a sessão', async () => {
    mockFetch(
      jsonResponse(404, {
        error: { code: 'session_not_found', message: 'Sessão não encontrada ou expirada.' },
      }),
    )

    await expect(deleteSession(SESSION_ID)).resolves.toBeUndefined()
  })

  it('apaga a sessão com 204 sem ler corpo', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }))

    await expect(deleteSession(SESSION_ID)).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenCalledWith(`/api/sessions/${SESSION_ID}`, { method: 'DELETE' })
  })
})
