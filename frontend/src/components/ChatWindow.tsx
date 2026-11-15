import { MESSAGES } from '../constants.ts'
import type { ChatSession, LocalMessage } from '../state/chatReducer.ts'
import MessageInput from './MessageInput.tsx'
import MessageList from './MessageList.tsx'
import SessionBadge from './SessionBadge.tsx'

interface ChatWindowProps {
  session: ChatSession
  messages: LocalMessage[]
  waiting: boolean
  onSend: (content: string) => void
  onRetry: (localId: string) => void
  onNewChat: () => void
}

export default function ChatWindow({ session, messages, waiting, onSend, onRetry, onNewChat }: ChatWindowProps) {
  return (
    <div className="flex h-dvh flex-col">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="hidden shrink-0 font-semibold sm:block">Chatbot Multiusuário</h1>
            <SessionBadge sessionId={session.id} persona={session.persona} />
          </div>
          <button
            type="button"
            onClick={onNewChat}
            className="shrink-0 rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-zinc-900"
          >
            {MESSAGES.newChat}
          </button>
        </div>
      </header>

      <MessageList messages={messages} waiting={waiting} onRetry={onRetry} />

      <footer className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 pt-3 pb-2">
          <MessageInput disabled={waiting} onSend={onSend} />
        </div>
      </footer>
    </div>
  )
}
