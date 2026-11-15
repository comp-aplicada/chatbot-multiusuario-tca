export const PERSONA_IDS = ['geral', 'juridico'] as const

export type PersonaId = (typeof PERSONA_IDS)[number]

export type Role = 'user' | 'assistant'

export interface ChatMessage {
  role: Role
  content: string
  created_at: string
}

export interface SessionCreated {
  session_id: string
  persona: PersonaId
  created_at: string
}

export interface SessionDetail extends SessionCreated {
  last_activity: string
  messages: ChatMessage[]
}

export interface SendMessageResponse {
  session_id: string
  reply: ChatMessage
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isPersonaId(value: unknown): value is PersonaId {
  return PERSONA_IDS.some((id) => id === value)
}

export function isChatMessage(value: unknown): value is ChatMessage {
  return (
    isRecord(value) &&
    (value.role === 'user' || value.role === 'assistant') &&
    typeof value.content === 'string' &&
    typeof value.created_at === 'string'
  )
}

export function isSessionCreated(value: unknown): value is SessionCreated {
  return (
    isRecord(value) &&
    typeof value.session_id === 'string' &&
    isPersonaId(value.persona) &&
    typeof value.created_at === 'string'
  )
}

export function isSessionDetail(value: unknown): value is SessionDetail {
  return (
    isSessionCreated(value) &&
    isRecord(value) &&
    typeof value.last_activity === 'string' &&
    Array.isArray(value.messages) &&
    value.messages.every(isChatMessage)
  )
}

export function isSendMessageResponse(value: unknown): value is SendMessageResponse {
  return isRecord(value) && typeof value.session_id === 'string' && isChatMessage(value.reply)
}

export function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    isRecord(value) &&
    isRecord(value.error) &&
    typeof value.error.code === 'string' &&
    typeof value.error.message === 'string'
  )
}
