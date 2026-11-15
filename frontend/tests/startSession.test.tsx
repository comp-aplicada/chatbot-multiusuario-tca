import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { STORAGE_KEY } from '../src/constants.ts'
import { SESSION_ID, jsonResponse, mockFetch, requestOf, sessionCreated, sessionDetail } from './helpers.ts'

describe('iniciar conversa', () => {
  it('cria a sessão com a persona escolhida, salva o ID e mostra o badge', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch(sessionCreated('juridico'))
    render(<App />)

    await user.click(screen.getByLabelText(/Orientação jurídica/))
    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))

    expect(await screen.findByText(SESSION_ID.slice(0, 8))).toBeInTheDocument()
    expect(screen.getByText('Jurídico')).toBeInTheDocument()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe(SESSION_ID)
    expect(requestOf(fetchMock, 0)).toEqual({ url: '/api/sessions', method: 'POST', body: { persona: 'juridico' } })
  })

  it('usa a persona geral por padrão', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch(sessionCreated('geral'))
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))

    await screen.findByText(SESSION_ID.slice(0, 8))
    expect(requestOf(fetchMock, 0).body).toEqual({ persona: 'geral' })
  })

  it('copia o ID completo ao clicar no badge', async () => {
    const user = userEvent.setup()
    mockFetch(sessionCreated())
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Iniciar conversa' }))
    await user.click(await screen.findByRole('button', { name: /Clique para copiar o ID/ }))

    expect(await screen.findByText('Copiado')).toBeInTheDocument()
    await expect(navigator.clipboard.readText()).resolves.toBe(SESSION_ID)
  })

  it('recarrega o histórico da sessão salva ao abrir a página (F5)', async () => {
    sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
    const fetchMock = mockFetch(
      sessionDetail([
        { role: 'user', content: 'Meu nome é Aurélio.' },
        { role: 'assistant', content: 'Prazer, Aurélio!' },
      ]),
    )
    render(<App />)

    expect(screen.getByText('Carregando conversa…')).toBeInTheDocument()
    expect(await screen.findByText('Prazer, Aurélio!')).toBeInTheDocument()
    expect(screen.getByText('Meu nome é Aurélio.')).toBeInTheDocument()
    expect(requestOf(fetchMock, 0)).toMatchObject({ url: `/api/sessions/${SESSION_ID}`, method: 'GET' })
  })

  it('nova conversa apaga a sessão no servidor e volta para a tela inicial', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
    const fetchMock = mockFetch(sessionDetail([]), new Response(null, { status: 204 }))
    render(<App />)

    await user.click(await screen.findByRole('button', { name: 'Nova conversa' }))

    expect(screen.getByRole('button', { name: 'Iniciar conversa' })).toBeInTheDocument()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(requestOf(fetchMock, 1)).toMatchObject({ url: `/api/sessions/${SESSION_ID}`, method: 'DELETE' })
  })

  it('nova conversa funciona mesmo se a sessão já tinha expirado no servidor', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
    mockFetch(
      sessionDetail([]),
      jsonResponse(404, { error: { code: 'session_not_found', message: 'Sessão não encontrada ou expirada.' } }),
    )
    render(<App />)

    await user.click(await screen.findByRole('button', { name: 'Nova conversa' }))

    expect(screen.getByRole('button', { name: 'Iniciar conversa' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
