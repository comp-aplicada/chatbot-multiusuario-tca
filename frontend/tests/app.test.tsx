import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { PERSONA_IDS } from '../src/api/types.ts'
import { MAX_CHARS } from '../src/constants.ts'

describe('App', () => {
  it('mostra o título e as duas personas', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Chatbot Multiusuário' })).toBeInTheDocument()
    expect(screen.getByText('Assistente geral')).toBeInTheDocument()
    expect(screen.getByText('Orientação jurídica')).toBeInTheDocument()
  })

  it('trava contra edição acidental das constantes copiadas do PRD', () => {
    expect(MAX_CHARS).toBe(2000)
    expect(PERSONA_IDS).toEqual(['geral', 'juridico'])
  })
})
