import { useEffect, useRef } from 'react'
import { MESSAGES } from '../constants.ts'
import type { LocalMessage } from '../state/chatReducer.ts'
import MessageBubble from './MessageBubble.tsx'

interface MessageListProps {
  messages: LocalMessage[]
  waiting: boolean
  onRetry: (localId: string) => void
}

export default function MessageList({ messages, waiting, onRetry }: MessageListProps) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const list = listRef.current
    if (list) {
      list.scrollTop = list.scrollHeight
    }
  }, [messages, waiting])

  return (
    <div ref={listRef} className="flex-1 overflow-y-auto">
      <ol aria-live="polite" aria-label="Mensagens" className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
        {messages.length === 0 && !waiting && (
          <li className="py-10 text-center text-sm text-zinc-500">Envie a primeira mensagem para começar.</li>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.localId} message={message} canRetry={!waiting} onRetry={onRetry} />
        ))}
        {waiting && (
          <li className="flex justify-start">
            <span className="animate-pulse rounded-2xl rounded-bl-md bg-white px-4 py-2 text-sm text-zinc-500 ring-1 ring-zinc-200">
              {MESSAGES.typing}
            </span>
          </li>
        )}
      </ol>
    </div>
  )
}
