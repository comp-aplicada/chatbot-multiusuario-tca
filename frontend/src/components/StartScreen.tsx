import { useState } from 'react'
import { PERSONA_IDS, type PersonaId } from '../api/types.ts'
import { DEFAULT_PERSONA, MESSAGES, PERSONAS } from '../constants.ts'

interface StartScreenProps {
  notice: string | null
  error: string | null
  starting: boolean
  onStart: (persona: PersonaId) => void
}

export default function StartScreen({ notice, error, starting, onStart }: StartScreenProps) {
  const [persona, setPersona] = useState<PersonaId>(DEFAULT_PERSONA)

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <form
        className="flex w-full max-w-xl flex-col gap-6"
        onSubmit={(event) => {
          event.preventDefault()
          onStart(persona)
        }}
      >
        <header className="flex flex-col gap-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Chatbot Multiusuário</h1>
          <p className="text-zinc-600">
            Converse com um assistente de IA. Cada aba do navegador é uma sessão diferente.
          </p>
        </header>

        {notice && (
          <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <p className="font-medium">{notice}</p>
            <p>Escolha uma persona para começar uma nova conversa.</p>
          </div>
        )}

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-3 text-sm font-medium text-zinc-700">Com quem você quer conversar?</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {PERSONA_IDS.map((id) => (
              <label
                key={id}
                className="flex cursor-pointer flex-col gap-1 rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-400 has-checked:border-zinc-900 has-checked:ring-1 has-checked:ring-zinc-900 has-focus-visible:ring-2 has-focus-visible:ring-zinc-900"
              >
                <input
                  type="radio"
                  name="persona"
                  value={id}
                  checked={persona === id}
                  onChange={() => setPersona(id)}
                  className="sr-only"
                />
                <span className="font-medium">{PERSONAS[id].label}</span>
                <span className="text-sm text-zinc-600">{PERSONAS[id].description}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={starting}
          className="h-12 rounded-xl bg-zinc-900 px-6 font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-wait disabled:opacity-60"
        >
          {starting ? 'Iniciando…' : MESSAGES.startChat}
        </button>
      </form>
    </main>
  )
}
