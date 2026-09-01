import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const { listThreads, getThread, sendEmail } = vi.hoisted(() => ({
  listThreads: vi.fn(), getThread: vi.fn(), sendEmail: vi.fn(),
}))

vi.mock('./api', () => ({ supportApi: { listThreads, getThread, sendEmail } }))

const detail = {
  session_id: 'THREAD-1001', status: 'completed' as const,
  messages: [{ message_id: 'EMAIL-1001', direction: 'inbound' as const, from_email: 'alice@example.test', subject: '<img src=x>', body: '<script>alert(1)</script>', sent_at: '2026-08-27T10:00:00Z' }],
}

describe('Support Inbox', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listThreads.mockResolvedValue({ threads: [{ session_id: 'THREAD-1001', subject: 'Order help', customer_email: 'alice@example.test', preview: 'Please help', last_message_at: '2026-08-27T10:00:00Z', status: 'completed' }] })
    getThread.mockResolvedValue(detail)
    sendEmail.mockResolvedValue(detail)
  })

  it('announces the loading state while the thread list request is pending', () => {
    listThreads.mockImplementation(() => new Promise(() => {}))

    render(<App />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading threads…')
  })

  it('shows an empty inbox state after loading a safely mappable empty thread list', async () => {
    listThreads.mockResolvedValue({ threads: [] })

    render(<App />)

    expect(await screen.findByText('No safely mappable support threads yet.')).toBeInTheDocument()
    expect(screen.queryByText('Loading threads…')).toBeNull()
  })

  it('shows a safe request-failure message when loading the inbox fails', async () => {
    listThreads.mockRejectedValue(new Error('network unavailable'))

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('The inbox could not be loaded.')
    expect(screen.queryByText('Loading threads…')).toBeNull()
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
    })))
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
    })))
    expect(screen.getByRole('button', { name: 'Sending…' })).toBeDisabled()
  })

  it('shows a safe pending notice without a continuation control', async () => {
    sendEmail.mockResolvedValue({ session_id: 'THREAD-1001', run_id: 'RUN-1001', status: 'approval_pending' })
    render(<App />)
    await screen.findByText('Order help')
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Refund' } })
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Please refund this.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send simulated email' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('pending administrative review'))
    expect(screen.queryByText(/resume|approve/i)).toBeNull()
  })
})
