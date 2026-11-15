import type { ChatMessage, PersonaId, Role } from '../api/types.ts'
import { MESSAGES } from '../constants.ts'

export type Screen = 'start' | 'loading' | 'chat'

export type MessageStatus = 'ok' | 'pending' | 'error'

export interface ChatSession {
  id: string
  persona: PersonaId
}

export interface LocalMessage {
  localId: string
  role: Role
  content: string
  created_at: string
  status: MessageStatus
  error: string | null
}

export interface ChatState {
  screen: Screen
  session: ChatSession | null
  messages: LocalMessage[]
  waiting: boolean
  starting: boolean
  notice: string | null
  error: string | null
}

export type ChatAction =
  | { type: 'start' }
  | { type: 'loaded'; session: ChatSession; messages: ChatMessage[] }
  | { type: 'send'; localId: string; content: string; createdAt: string }
  | { type: 'reply'; localId: string; reply: ChatMessage; replyId: string }
  | { type: 'fail'; localId: string; error: string }
  | { type: 'retry'; localId: string }
  | { type: 'screenError'; error: string }
  | { type: 'reload' }
  | { type: 'expired' }
  | { type: 'reset' }

export const startState: ChatState = {
  screen: 'start',
  session: null,
  messages: [],
  waiting: false,
  starting: false,
  notice: null,
  error: null,
}

export function initialState(storedSessionId: string | null): ChatState {
  return storedSessionId ? { ...startState, screen: 'loading' } : startState
}

function fromServer(message: ChatMessage, localId: string): LocalMessage {
  return { ...message, localId, status: 'ok', error: null }
}

function updateMessage(
  messages: LocalMessage[],
  localId: string,
  changes: Partial<LocalMessage>,
): LocalMessage[] {
  return messages.map((message) => (message.localId === localId ? { ...message, ...changes } : message))
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'start':
      return { ...state, starting: true, notice: null, error: null }
    case 'loaded':
      return {
        ...startState,
        screen: 'chat',
        session: action.session,
        messages: action.messages.map((message, index) => fromServer(message, `server-${index}`)),
      }
    case 'send':
      return {
        ...state,
        waiting: true,
        messages: [
          ...state.messages,
          {
            localId: action.localId,
            role: 'user',
            content: action.content,
            created_at: action.createdAt,
            status: 'pending',
            error: null,
          },
        ],
      }
    case 'reply':
      return {
        ...state,
        waiting: false,
        messages: [
          ...updateMessage(state.messages, action.localId, { status: 'ok', error: null }),
          fromServer(action.reply, action.replyId),
        ],
      }
    case 'fail':
      return {
        ...state,
        waiting: false,
        messages: updateMessage(state.messages, action.localId, { status: 'error', error: action.error }),
      }
    case 'retry': {
      const failed = state.messages.find((message) => message.localId === action.localId)
      if (!failed || state.waiting) {
        return state
      }
      return {
        ...state,
        waiting: true,
        messages: [
          ...state.messages.filter((message) => message.localId !== action.localId),
          { ...failed, status: 'pending', error: null },
        ],
      }
    }
    case 'screenError':
      return { ...state, starting: false, error: action.error }
    case 'reload':
      return { ...state, screen: 'loading', error: null }
    case 'expired':
      return { ...startState, notice: MESSAGES.sessionExpired }
    case 'reset':
      return startState
  }
}
