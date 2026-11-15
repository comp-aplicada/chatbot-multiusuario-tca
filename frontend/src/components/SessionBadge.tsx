import { useState } from 'react'
import type { PersonaId } from '../api/types.ts'
import { MESSAGES, PERSONAS } from '../constants.ts'

const COPIED_MS = 2000

interface SessionBadgeProps {
  sessionId: string
  persona: PersonaId
}

export default function SessionBadge({ sessionId, persona }: SessionBadgeProps) {
  const [copied, setCopied] = useState(false)

  function showCopied() {
    setCopied(true)
    window.setTimeout(() => setCopied(false), COPIED_MS)
  }

  function copy() {
    if (!navigator.clipboard) {
      return
    }
    navigator.clipboard.writeText(sessionId).then(showCopied, () => undefined)
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={`ID da sessão: ${sessionId}`}
      aria-label={`${PERSONAS[persona].label}, sessão ${sessionId}. Clique para copiar o ID.`}
      className="flex min-w-0 items-center gap-2 rounded-lg bg-zinc-100 px-3 py-2 text-left text-sm transition-colors hover:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-zinc-900"
    >
      <span className="truncate font-medium sm:hidden">{PERSONAS[persona].shortLabel}</span>
      <span className="hidden truncate font-medium sm:inline">{PERSONAS[persona].label}</span>
      <span aria-live="polite" className="shrink-0 font-mono text-zinc-600">
        {copied ? MESSAGES.copied : sessionId.slice(0, 8)}
      </span>
    </button>
  )
}
