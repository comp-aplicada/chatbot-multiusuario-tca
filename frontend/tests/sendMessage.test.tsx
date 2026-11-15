import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../src/App.tsx'
import { MAX_CHARS, MESSAGES, STORAGE_KEY } from '../src/constants.ts'
import { SESSION_ID, deferred, mockFetch, reply, requestOf, sessionDetail } from './helpers.ts'

async function openChat(...responses: (Response | Promise<Response>)[]) {
  sessionStorage.setItem(STORAGE_KEY, SESSION_ID)
  const fetchMock = mockFetch(sessionDetail([]), ...responses)
  const user = userEvent.setup()
  render(<App />)
  const input = await screen.findByLabelText('Mensagem')
  return { fetchMock, user, input }
}

describe('enviar mensagem', () => {
  it('mostra a pergunta na hora, desabilita o input enquanto aguarda e renderiza a resposta', async () => {
    const pending = deferred<Response>()
    const { fetchMock, user, input } = await openChat(pending.promise)

    await user.type(input, 'O que é computação em nuvem?')
    await user.click(screen.getByRole('button', { name: 'Enviar' }))

    expect(screen.getByText('O que é computação em nuvem?')).toBeInTheDocument()
    expect(screen.getByText(MESSAGES.typing)).toBeInTheDocument()
    expect(input).toBeDisabled()
    expect(input).toHaveValue('')

    pending.resolve(reply('É usar recursos de computação pela internet.'))

    expect(await screen.findByText('É usar recursos de computação pela internet.')).toBeInTheDocument()
    expect(screen.queryByText(MESSAGES.typing)).not.toBeInTheDocument()
    expect(input).toBeEnabled()
    expect(input).toHaveFocus()
    expect(requestOf(fetchMock, 1)).toEqual({
      url: `/api/sessions/${SESSION_ID}/messages`,
      method: 'POST',
      body: { content: 'O que é computação em nuvem?' },
    })
  })

  it('Enter envia', async () => {
    const { fetchMock, user, input } = await openChat(reply('ok'))

    await user.type(input, 'Olá{Enter}')

    expect(await screen.findByText('ok')).toBeInTheDocument()
    expect(requestOf(fetchMock, 1).body).toEqual({ content: 'Olá' })
  })

  it('Shift+Enter quebra a linha e não envia', async () => {
    const { fetchMock, user, input } = await openChat()

    await user.type(input, 'linha 1{Shift>}{Enter}{/Shift}linha 2')

    expect(input).toHaveValue('linha 1\nlinha 2')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('não envia texto só com espaços', async () => {
    const { fetchMock, user, input } = await openChat()

    await user.type(input, '   {Enter}')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
  })

  it('mostra o contador e não deixa passar de 2000 caracteres', async () => {
    const { user, input } = await openChat()

    await user.type(input, 'abc')
    expect(screen.getByText(`3/${MAX_CHARS}`)).toBeInTheDocument()

    await user.clear(input)
    await user.click(input)
    await user.paste('x'.repeat(MAX_CHARS + 50))

    expect(input).toHaveValue('x'.repeat(MAX_CHARS))
    expect(screen.getByText(`${MAX_CHARS}/${MAX_CHARS}`)).toBeInTheDocument()
  })

  it('mostra a pergunta do usuário como texto puro, sem Markdown', async () => {
    const { user, input } = await openChat(reply('ok'))

    await user.type(input, '**não é negrito**{Enter}')

    expect(await screen.findByText('**não é negrito**')).toBeInTheDocument()
    expect(document.querySelector('strong')).toBeNull()
  })
})
