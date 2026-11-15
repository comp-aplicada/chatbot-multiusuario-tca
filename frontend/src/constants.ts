import type { PersonaId } from './api/types.ts'

export const MAX_CHARS = 2000

export const STORAGE_KEY = 'chat.session_id'

export interface Persona {
  label: string
  shortLabel: string
  description: string
}

export const PERSONAS: Readonly<Record<PersonaId, Persona>> = {
  geral: {
    label: 'Assistente geral',
    shortLabel: 'Geral',
    description: 'Perguntas sobre qualquer assunto, com respostas claras e objetivas.',
  },
  juridico: {
    label: 'Orientação jurídica',
    shortLabel: 'Jurídico',
    description: 'Dúvidas gerais sobre o direito brasileiro, em linguagem acessível.',
  },
}

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
