export const PERSONA_IDS = ['geral', 'juridico'] as const

export type PersonaId = (typeof PERSONA_IDS)[number]
