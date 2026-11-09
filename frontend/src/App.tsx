import { PERSONAS } from './constants.ts'

export default function App() {
  return (
    <main className="mx-auto flex h-dvh max-w-3xl flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-center text-2xl font-semibold">Chatbot Multiusuário</h1>
      <p className="text-center text-zinc-600">
        Converse com um assistente de IA. Cada aba do navegador é uma sessão diferente.
      </p>
      <ul className="grid w-full gap-3 sm:grid-cols-2">
        {PERSONAS.map((persona) => (
          <li key={persona.id} className="rounded-xl border border-zinc-200 bg-white p-4">
            <p className="font-medium">{persona.label}</p>
            <p className="text-sm text-zinc-600">{persona.description}</p>
          </li>
        ))}
      </ul>
    </main>
  )
}
