import { useCallback, useEffect, useReducer } from 'react'
import { ApiError, createSession, deleteSession, getSession, sendMessage } from './api/client.ts'
import type { PersonaId } from './api/types.ts'
import ChatWindow from './components/ChatWindow.tsx'
import LoadingScreen from './components/LoadingScreen.tsx'
import StartScreen from './components/StartScreen.tsx'
import { MESSAGES } from './constants.ts'
import { chatReducer, initialState } from './state/chatReducer.ts'
import { clearSessionId, readSessionId, saveSessionId } from './state/storedSession.ts'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : MESSAGES.networkError
}

function isSessionGone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

export default function App() {
  const [state, dispatch] = useReducer(chatReducer, null, () => initialState(readSessionId()))

  const expire = useCallback(() => {
    clearSessionId()
    dispatch({ type: 'expired' })
  }, [])

  const restore = useCallback(async () => {
    const sessionId = readSessionId()
    if (!sessionId) {
      dispatch({ type: 'reset' })
      return
    }
    try {
      const detail = await getSession(sessionId)
      dispatch({
        type: 'loaded',
        session: { id: detail.session_id, persona: detail.persona },
        messages: detail.messages,
      })
    } catch (error) {
      if (isSessionGone(error)) {
        expire()
      } else {
        dispatch({ type: 'screenError', error: errorMessage(error) })
      }
    }
  }, [expire])

  useEffect(() => {
    if (readSessionId()) {
      void restore()
    }
  }, [restore])

  async function startChat(persona: PersonaId) {
    dispatch({ type: 'start' })
    try {
      const created = await createSession(persona)
      saveSessionId(created.session_id)
      dispatch({ type: 'loaded', session: { id: created.session_id, persona: created.persona }, messages: [] })
    } catch (error) {
      dispatch({ type: 'screenError', error: errorMessage(error) })
    }
  }

  async function deliver(sessionId: string, localId: string, content: string) {
    try {
      const response = await sendMessage(sessionId, content)
      if (readSessionId() === sessionId) {
        dispatch({ type: 'reply', localId, reply: response.reply, replyId: crypto.randomUUID() })
      }
    } catch (error) {
      if (readSessionId() !== sessionId) {
        return
      }
      if (isSessionGone(error)) {
        expire()
      } else {
        dispatch({ type: 'fail', localId, error: errorMessage(error) })
      }
    }
  }

  function send(content: string) {
    if (!state.session || state.waiting) {
      return
    }
    const localId = crypto.randomUUID()
    dispatch({ type: 'send', localId, content, createdAt: new Date().toISOString() })
    void deliver(state.session.id, localId, content)
  }

  function retry(localId: string) {
    const failed = state.messages.find((message) => message.localId === localId)
    if (!state.session || !failed || state.waiting) {
      return
    }
    dispatch({ type: 'retry', localId })
    void deliver(state.session.id, localId, failed.content)
  }

  function newChat() {
    const sessionId = state.session?.id ?? readSessionId()
    clearSessionId()
    dispatch({ type: 'reset' })
    if (sessionId) {
      void deleteSession(sessionId).catch(() => undefined)
    }
  }

  function reload() {
    dispatch({ type: 'reload' })
    void restore()
  }

  if (state.screen === 'loading') {
    return <LoadingScreen error={state.error} onRetry={reload} onNewChat={newChat} />
  }

  if (state.screen === 'chat' && state.session) {
    return (
      <ChatWindow
        session={state.session}
        messages={state.messages}
        waiting={state.waiting}
        onSend={send}
        onRetry={retry}
        onNewChat={newChat}
      />
    )
  }

  return <StartScreen notice={state.notice} error={state.error} starting={state.starting} onStart={startChat} />
}
