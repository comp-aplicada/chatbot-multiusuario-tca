import { MESSAGES } from '../constants.ts'
import {
  isApiErrorBody,
  isSendMessageResponse,
  isSessionCreated,
  isSessionDetail,
  type PersonaId,
  type SendMessageResponse,
  type SessionCreated,
  type SessionDetail,
} from './types.ts'

export const NETWORK_ERROR = 'network_error'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

function networkError(status: number): ApiError {
  return new ApiError(status, NETWORK_ERROR, MESSAGES.networkError)
}

function sessionPath(sessionId: string): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}`
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init)
  } catch {
    throw networkError(0)
  }
}

async function readBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw networkError(response.status)
  }
}

function toApiError(status: number, body: unknown): ApiError {
  if (!isApiErrorBody(body)) {
    return networkError(status)
  }
  return new ApiError(status, body.error.code, body.error.message)
}

async function parse<T>(response: Response, isExpected: (value: unknown) => value is T): Promise<T> {
  const body = await readBody(response)
  if (response.ok && isExpected(body)) {
    return body
  }
  throw toApiError(response.status, body)
}

export async function createSession(persona: PersonaId): Promise<SessionCreated> {
  const response = await request('/api/sessions', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ persona }),
  })
  return parse(response, isSessionCreated)
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await request(sessionPath(sessionId))
  return parse(response, isSessionDetail)
}

export async function sendMessage(sessionId: string, content: string): Promise<SendMessageResponse> {
  const response = await request(`${sessionPath(sessionId)}/messages`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ content }),
  })
  return parse(response, isSendMessageResponse)
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await request(sessionPath(sessionId), { method: 'DELETE' })
  if (response.ok || response.status === 404) {
    return
  }
  throw toApiError(response.status, await readBody(response))
}
