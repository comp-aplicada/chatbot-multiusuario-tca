import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { MAX_CHARS, PERSONAS } from '../src/constants.ts'

describe('App', () => {
  it('mostra o título e as duas personas', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Chatbot Multiusuário' })).toBeInTheDocument()
    expect(screen.getByText('Assistente geral')).toBeInTheDocument()
    expect(screen.getByText('Orientação jurídica')).toBeInTheDocument()
  })

  it('mantém as constantes alinhadas com o contrato da API', () => {
    expect(MAX_CHARS).toBe(2000)
    expect(PERSONAS.map((persona) => persona.id)).toEqual(['geral', 'juridico'])
  })
})
