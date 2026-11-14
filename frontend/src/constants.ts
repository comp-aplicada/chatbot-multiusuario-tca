export const MAX_CHARS = 2000

export const STORAGE_KEY = 'chat.session_id'

export type PersonaId = 'geral' | 'juridico'

export interface Persona {
  id: PersonaId
  label: string
  description: string
}

export const PERSONAS: readonly Persona[] = [
  {
    id: 'geral',
    label: 'Assistente geral',
    description: 'Perguntas sobre qualquer assunto, com respostas claras e objetivas.',
  },
  {
    id: 'juridico',
    label: 'Orientação jurídica',
    description: 'Dúvidas gerais sobre o direito brasileiro, em linguagem acessível.',
  },
]

export const DEFAULT_PERSONA: PersonaId = 'geral'

export const MESSAGES = {
  sessionExpired: 'Sua sessão expirou',
  networkError: 'Não foi possível falar com o servidor. Tente novamente.',
  typing: 'digitando…',
  retry: 'Tentar de novo',
  startChat: 'Iniciar conversa',
  newChat: 'Nova conversa',
  copied: 'Copiado',
} as const
