import Markdown, { type Components } from 'react-markdown'
import { MESSAGES } from '../constants.ts'
import type { LocalMessage } from '../state/chatReducer.ts'

const markdownComponents: Components = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
}

interface MessageBubbleProps {
  message: LocalMessage
  canRetry: boolean
  onRetry: (localId: string) => void
}

export default function MessageBubble({ message, canRetry, onRetry }: MessageBubbleProps) {
  if (message.role === 'assistant') {
    return (
      <li className="flex justify-start">
        <div className="markdown max-w-5/6 min-w-0 rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm ring-1 ring-zinc-200">
          <Markdown components={markdownComponents}>{message.content}</Markdown>
        </div>
      </li>
    )
  }

  const failed = message.status === 'error'

  return (
    <li className="flex flex-col items-end gap-2">
      <p
        className={`max-w-5/6 rounded-2xl rounded-br-md px-4 py-2 whitespace-pre-wrap wrap-break-word text-white ${
          failed ? 'bg-red-700' : 'bg-zinc-900'
        } ${message.status === 'pending' ? 'opacity-70' : ''}`}
      >
        {message.content}
      </p>
      {failed && (
        <div role="alert" className="flex max-w-5/6 flex-wrap items-center justify-end gap-2 text-right text-sm text-red-700">
          <span>{message.error}</span>
          <button
            type="button"
            disabled={!canRetry}
            onClick={() => onRetry(message.localId)}
            className="rounded-lg border border-red-300 bg-white px-3 py-1 font-medium transition-colors hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-red-700 disabled:opacity-50"
          >
            {MESSAGES.retry}
          </button>
        </div>
      )}
    </li>
  )
}
