import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { MAX_CHARS } from '../constants.ts'

const WARNING_CHARS = MAX_CHARS - 200

interface MessageInputProps {
  disabled: boolean
  onSend: (content: string) => void
}

export default function MessageInput({ disabled, onSend }: MessageInputProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const content = text.trim()
  const canSend = !disabled && content.length > 0 && text.length <= MAX_CHARS

  useEffect(() => {
    if (!disabled) {
      textareaRef.current?.focus()
    }
  }, [disabled])

  function submit() {
    if (!canSend) {
      return
    }
    onSend(content)
    setText('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="flex flex-col gap-1"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor="message-input" className="sr-only">
        Mensagem
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id="message-input"
          ref={textareaRef}
          rows={1}
          value={text}
          maxLength={MAX_CHARS}
          disabled={disabled}
          placeholder="Digite sua mensagem"
          onChange={(event) => setText(event.target.value.slice(0, MAX_CHARS))}
          onKeyDown={handleKeyDown}
          className="field-sizing-content max-h-36 min-h-12 flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-3 py-3 text-base leading-6 focus:border-zinc-900 focus:outline-none disabled:bg-zinc-100 disabled:text-zinc-500"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="h-12 shrink-0 rounded-xl bg-zinc-900 px-4 font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:opacity-40"
        >
          Enviar
        </button>
      </div>
      <p
        className={`text-right text-xs tabular-nums ${text.length >= WARNING_CHARS ? 'text-red-600' : 'text-zinc-500'}`}
      >
        {text.length}/{MAX_CHARS}
      </p>
    </form>
  )
}
