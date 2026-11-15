import { MESSAGES } from '../constants.ts'

interface LoadingScreenProps {
  error: string | null
  onRetry: () => void
  onNewChat: () => void
}

export default function LoadingScreen({ error, onRetry, onNewChat }: LoadingScreenProps) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      {error ? (
        <div className="flex max-w-sm flex-col items-center gap-4 text-center">
          <p role="alert" className="text-red-800">
            {error}
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg bg-zinc-900 px-4 py-2 font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
            >
              {MESSAGES.retry}
            </button>
            <button
              type="button"
              onClick={onNewChat}
              className="rounded-lg border border-zinc-300 px-4 py-2 font-medium transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-zinc-900"
            >
              {MESSAGES.newChat}
            </button>
          </div>
        </div>
      ) : (
        <p role="status" className="animate-pulse text-zinc-500">
          Carregando conversa…
        </p>
      )}
    </main>
  )
}
