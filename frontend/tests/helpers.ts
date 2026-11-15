import { vi } from 'vitest'

export const SESSION_ID = '3f2a9c1e-8b7d-4c1a-9e2f-0a1b2c3d4e5f'
export const CREATED_AT = '2026-11-11T14:00:00Z'

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function apiError(status: number, code: string, message: string): Response {
  return jsonResponse(status, { error: { code, message } })
}

export function sessionCreated(persona: string = 'geral', sessionId: string = SESSION_ID): Response {
  return jsonResponse(201, { session_id: sessionId, persona, created_at: CREATED_AT })
}

export function sessionDetail(
  messages: { role: 'user' | 'assistant'; content: string }[],
  persona: string = 'geral',
): Response {
  return jsonResponse(200, {
    session_id: SESSION_ID,
    persona,
    created_at: CREATED_AT,
    last_activity: CREATED_AT,
    messages: messages.map((message) => ({ ...message, created_at: CREATED_AT })),
  })
}

export function reply(content: string): Response {
  return jsonResponse(200, {
    session_id: SESSION_ID,
    reply: { role: 'assistant', content, created_at: CREATED_AT },
  })
}

export function deferred<T>() {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

type FetchResult = Response | Promise<Response> | Error

export function mockFetch(...results: FetchResult[]) {
  const fetchMock = vi.spyOn(globalThis, 'fetch')
  for (const result of results) {
    if (result instanceof Error) {
      fetchMock.mockRejectedValueOnce(result)
    } else {
      fetchMock.mockImplementationOnce(() => Promise.resolve(result))
    }
  }
  return fetchMock
}

export function requestOf(fetchMock: ReturnType<typeof mockFetch>, index: number) {
  const call = fetchMock.mock.calls[index]
  if (!call) {
    throw new Error(`fetch não foi chamado ${index + 1} vezes`)
  }
  const [url, init] = call
  const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
  return { url: String(url), method: init?.method ?? 'GET', body }
}
