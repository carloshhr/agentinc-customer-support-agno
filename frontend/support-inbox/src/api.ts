export type ThreadStatus = 'completed' | 'approval_pending' | 'incomplete'

export interface ThreadSummary {
  session_id: string
  subject: string
  customer_email: string
  preview: string
  last_message_at: string
  status: ThreadStatus
}

export interface InboxMessage {
  message_id: string
  direction: 'inbound' | 'outbound'
  from_email: string
  subject: string
  body: string
  sent_at: string
  category?: string | null
  issue_code?: string | null
  outcome?: string | null
}

export interface ThreadDetail {
  session_id: string
  status: ThreadStatus
  messages: InboxMessage[]
}

export interface SendEmailRequest {
  thread_id: string
  message_id: string
  from_email: string
  subject: string
  body: string
}

export interface PendingSend {
  session_id: string
  run_id: string | null
  status: 'approval_pending'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok && response.status !== 202) throw new Error('The support inbox request failed.')
  return response.json() as Promise<T>
}

export const supportApi = {
  listThreads: () => request<{ threads: ThreadSummary[] }>('/api/support/threads'),
  getThread: (sessionId: string) => request<ThreadDetail>(`/api/support/threads/${encodeURIComponent(sessionId)}`),
  sendEmail: (email: SendEmailRequest) =>
    request<ThreadDetail | PendingSend>('/api/support/emails', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(email),
    }),
}
