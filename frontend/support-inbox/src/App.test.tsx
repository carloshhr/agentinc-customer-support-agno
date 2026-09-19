import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const { getSession, login, logout, listThreads, getThread, sendEmail } = vi.hoisted(() => ({
  getSession: vi.fn(), login: vi.fn(), logout: vi.fn(), listThreads: vi.fn(), getThread: vi.fn(), sendEmail: vi.fn(),
}))

vi.mock('./api', () => ({ supportApi: { getSession, login, logout, listThreads, getThread, sendEmail } }))

const detail = {
  session_id: 'THREAD-1001', status: 'completed' as const,
  messages: [{ message_id: 'EMAIL-1001', direction: 'inbound' as const, from_email: 'alice@example.test', subject: '<img src=x>', body: '<script>alert(1)</script>', sent_at: '2026-08-27T10:00:00Z' }],
}

describe('Support Inbox', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    getSession.mockResolvedValue({ operator: { id: 'OP-1', username: 'alice', display_name: 'Alice' }, csrf_token: 'csrf-1' })
    login.mockResolvedValue({ operator: { id: 'OP-1', username: 'alice', display_name: 'Alice' }, csrf_token: 'csrf-1' })
    logout.mockResolvedValue(undefined)
    listThreads.mockResolvedValue({ threads: [{ session_id: 'THREAD-1001', subject: 'Order help', customer_email: 'alice@example.test', preview: 'Please help', last_message_at: '2026-08-27T10:00:00Z', status: 'completed' }] })
    getThread.mockResolvedValue(detail)
    sendEmail.mockResolvedValue(detail)
  })

  it('withholds inbox requests and renders the signed-out flow until session validation succeeds', async () => {
    getSession.mockRejectedValueOnce({ status: 401, kind: 'unauthorized' })

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in to Support Inbox' })).toBeInTheDocument()
    expect(listThreads).not.toHaveBeenCalled()
  })

  it('restores a session, shows the operator, and then loads the inbox', async () => {
    render(<App />)

    expect(await screen.findByText('Signed in as Alice')).toBeInTheDocument()
    expect(await screen.findByText('Order help')).toBeInTheDocument()
    expect(getSession).toHaveBeenCalledOnce()
    expect(listThreads).toHaveBeenCalledOnce()
  })

  it.each([
    [{ status: 403, kind: 'forbidden' }, 'You are not allowed to use Support Inbox.'],
    [{ status: 429, kind: 'rate_limited' }, 'Too many requests. Please try again later.'],
    [{ status: 502, kind: 'gateway' }, 'Support service is temporarily unavailable.'],
  ] as const)('renders a safe authentication state for %s', async (failure, message) => {
    getSession.mockRejectedValueOnce(failure)

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(listThreads).not.toHaveBeenCalled()
  })

  it('clears the session and returns to sign-in when a request expires', async () => {
    listThreads.mockRejectedValueOnce({ status: 401, kind: 'unauthorized' })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign in to Support Inbox' })).toBeInTheDocument()
    expect(screen.getByText('Your session expired. Please sign in again.')).toBeInTheDocument()
  })

  it('logs out and clears the in-memory session state', async () => {
    render(<App />)
    await screen.findByText('Order help')

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    await waitFor(() => expect(logout).toHaveBeenCalledWith('csrf-1'))
    expect(await screen.findByRole('heading', { name: 'Sign in to Support Inbox' })).toBeInTheDocument()
    expect(screen.queryByText('Order help')).toBeNull()
  })

  it('shows an indistinguishable login failure and clears the password field', async () => {
    getSession.mockRejectedValueOnce({ status: 401, kind: 'unauthorized' })
    login.mockRejectedValueOnce({ status: 401, kind: 'unauthorized' })
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in to Support Inbox' })

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'unknown' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'not-a-real-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('announces the loading state while the thread list request is pending', () => {
    listThreads.mockImplementation(() => new Promise(() => {}))

    render(<App />)

    expect(screen.getByRole('status')).toHaveTextContent('Checking session…')
  })

  it('shows an empty inbox state after loading a safely mappable empty thread list', async () => {
    listThreads.mockResolvedValue({ threads: [] })

    render(<App />)

    expect(await screen.findByText('No safely mappable support threads yet.')).toBeInTheDocument()
    expect(screen.queryByText('Loading threads…')).toBeNull()
  })

  it('retries a failed inbox load from the visible retry action', async () => {
    listThreads.mockRejectedValueOnce(new Error('network unavailable')).mockResolvedValueOnce({
      threads: [{ session_id: 'THREAD-1001', subject: 'Order help', customer_email: 'alice@example.test', preview: 'Please help', last_message_at: '2026-08-27T10:00:00Z', status: 'completed' }],
    })

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('The inbox could not be loaded.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry inbox' }))

    expect(await screen.findByText('Order help')).toBeInTheDocument()
    expect(listThreads).toHaveBeenCalledTimes(2)
  })

  it('refreshes the inbox and selected thread with the existing APIs', async () => {
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.click(screen.getByText('Order help'))
    await screen.findByRole('region', { name: 'Thread detail' })

    fireEvent.click(screen.getByRole('button', { name: 'Refresh inbox and selected thread' }))

    await waitFor(() => expect(listThreads).toHaveBeenCalledTimes(2))
    expect(getThread).toHaveBeenCalledTimes(2)
  })

  it('retries a failed selected thread load', async () => {
    getThread.mockRejectedValueOnce(new Error('network unavailable')).mockResolvedValueOnce(detail)
    render(<App />)
    await screen.findByText('Order help')

    fireEvent.click(screen.getByText('Order help'))
    expect(await screen.findByRole('alert')).toHaveTextContent('This thread could not be loaded.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry thread' }))

    expect(await screen.findByRole('region', { name: 'Thread detail' })).toBeInTheDocument()
    expect(getThread).toHaveBeenCalledTimes(2)
  })

  it('selects a thread, renders model content as text, and exposes exactly Email and JSON tabs', async () => {
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.click(screen.getByText('Order help'))
    await screen.findByText('<script>alert(1)</script>')
    expect(document.querySelector('script')).toBeNull()
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['Email', 'JSON'])
    fireEvent.click(screen.getByRole('tab', { name: 'JSON' }))
    expect(await screen.findByText(/"session_id": "THREAD-1001"/)).toBeInTheDocument()
  })

  it('returns to the mobile list and keeps compose validation local', async () => {
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.click(screen.getByText('Order help'))
    await screen.findByRole('button', { name: 'Back to inbox' })
    fireEvent.click(screen.getByRole('button', { name: 'Back to inbox' }))
    expect(screen.queryByLabelText('Thread detail')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Send simulated email' }))
    expect(screen.getByRole('alert')).toHaveTextContent('required')
    expect(sendEmail).not.toHaveBeenCalled()
  })

  it('uses the selected support session unchanged when sending a reply', async () => {
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.click(screen.getByText('Order help'))
    const detailRegion = await screen.findByRole('region', { name: 'Thread detail' })
    fireEvent.change(within(detailRegion).getByLabelText('Subject'), { target: { value: 'Re: Order help' } })
    fireEvent.change(within(detailRegion).getByLabelText('Message'), { target: { value: 'Please confirm delivery.' } })
    fireEvent.click(within(detailRegion).getByRole('button', { name: 'Send simulated email' }))

    await waitFor(() => expect(sendEmail).toHaveBeenCalledWith(expect.objectContaining({
      thread_id: 'THREAD-1001',
      subject: 'Re: Order help',
      body: 'Please confirm delivery.',
    }), 'csrf-1'))
  })

  it('disables sending and announces progress while a simulated email request is in progress', async () => {
    sendEmail.mockImplementation(() => new Promise(() => {}))
    render(<App />)

    await screen.findByText('Order help')
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Order update' } })
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Could you share an update?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send simulated email' }))

    await waitFor(() => expect(sendEmail).toHaveBeenCalledWith(expect.objectContaining({
      subject: 'Order update',
      body: 'Could you share an update?',
    }), 'csrf-1'))
    expect(screen.getByRole('button', { name: 'Sending…' })).toBeDisabled()
  })

  it('explains specialist routing and compose versus reply behavior', async () => {
    render(<App />)

    expect(await screen.findByText(/Customer Support routes requests to Order Support, Product Support, and Returns & Refunds Support/)).toBeInTheDocument()
    expect(screen.getByText(/Compose creates a new simulated customer thread; Reply continues the selected thread/)).toBeInTheDocument()
  })

  it('renders approval pending as an administrative read-only state without continuation controls', async () => {
    listThreads.mockResolvedValue({ threads: [{ session_id: 'THREAD-1001', subject: 'Order help', customer_email: 'alice@example.test', preview: 'Please help', last_message_at: '2026-08-27T10:00:00Z', status: 'approval_pending' }] })
    getThread.mockResolvedValue({ ...detail, status: 'approval_pending' })
    render(<App />)
    await screen.findByText('Awaiting administrative review')
    fireEvent.click(screen.getByText('Order help'))

    expect(await screen.findByText('Awaiting administrative review')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Reply' })).toBeNull()
    expect(screen.queryByText(/resume|approve|reject/i)).toBeNull()
  })

  it('shows a safe pending notice without a continuation control', async () => {
    sendEmail.mockResolvedValue({ session_id: 'THREAD-1001', run_id: 'RUN-1001', status: 'approval_pending' })
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Refund' } })
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Please refund this.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send simulated email' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Awaiting administrative review'))
    expect(screen.queryByText(/resume|approve|reject/i)).toBeNull()
  })
})
