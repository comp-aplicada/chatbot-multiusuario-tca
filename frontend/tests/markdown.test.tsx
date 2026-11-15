import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { STORAGE_KEY } from '../src/constants.ts'
import { SESSION_ID, mockFetch, sessionDetail } from './helpers.ts'

async function renderAssistant(content: string) {
  sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
  mockFetch(sessionDetail([{ role: 'assistant', content }]))
  const { container } = render(<App />)
  await screen.findByRole('button', { name: 'Nova conversa' })
  return container
}

describe('Markdown nas respostas do assistente', () => {
  it('renderiza **x** como <strong>x</strong>', async () => {
    const container = await renderAssistant('Isto é **x**.')

    const strong = container.querySelector('strong')
    expect(strong).not.toBeNull()
    expect(strong).toHaveTextContent('x')
  })

  it('renderiza listas e código', async () => {
    const container = await renderAssistant('- um\n- dois\n\n```\nprint(1)\n```')

    expect(container.querySelectorAll('ul li')).toHaveLength(2)
    expect(container.querySelector('pre code')).toHaveTextContent('print(1)')
  })

  it('mostra <script> como texto e não coloca nenhum script no DOM', async () => {
    const container = await renderAssistant('Antes <script>alert("xss")</script> depois')

    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText(/<script>alert\("xss"\)<\/script>/)).toBeInTheDocument()
  })

  it('não interpreta HTML com atributos de evento', async () => {
    const container = await renderAssistant('<img src="x" onerror="alert(1)">')

    expect(container.querySelector('img')).toBeNull()
  })

  it('abre links em outra aba sem dar acesso à página', async () => {
    const container = await renderAssistant('[PRD](https://example.com)')

    const link = container.querySelector('a')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer')
  })
})
