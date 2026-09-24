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

export interface Operator {
  id: string
  username: string
  display_name: string
}

export interface SessionResponse {
  operator: Operator
  csrf_token: string
}

export type SupportErrorKind = 'unauthorized' | 'forbidden' | 'rate_limited' | 'gateway' | 'request'

export class SupportApiError extends Error {
  constructor(public readonly status: number, public readonly kind: SupportErrorKind) {
    super('The support inbox request failed.')
    this.name = 'SupportApiError'
  }
}

const BFF_ORIGIN = (import.meta.env.VITE_SUPPORT_API_ORIGIN ?? '').replace(/\/$/, '')

function errorKind(status: number): SupportErrorKind {
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 429) return 'rate_limited'
  if (status >= 500 || status === 0) return 'gateway'
  return 'request'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!BFF_ORIGIN) throw new SupportApiError(0, 'gateway')
  try {
    const response = await fetch(`${BFF_ORIGIN}${path}`, { ...init, credentials: 'include' })
    if (!response.ok && response.status !== 202) throw new SupportApiError(response.status, errorKind(response.status))
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof SupportApiError) throw error
    throw new SupportApiError(0, 'gateway')
  }
}

export const supportApi = {
  getSession: () => request<SessionResponse>('/auth/session'),
  login: (username: string, password: string) => request<SessionResponse>('/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }),
  }),
  logout: (csrfToken: string) => request<void>('/auth/logout', {
    method: 'POST', headers: { 'X-CSRF-Token': csrfToken },
  }),
  listThreads: () => request<{ threads: ThreadSummary[] }>('/api/support/threads'),
  getThread: (sessionId: string) => request<ThreadDetail>(`/api/support/threads/${encodeURIComponent(sessionId)}`),
  sendEmail: (email: SendEmailRequest, csrfToken: string) =>
    request<ThreadDetail | PendingSend>('/api/support/emails', withCsrf({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(email),
    }, csrfToken)),
}

export function withCsrf(init: RequestInit, csrfToken: string): RequestInit {
  return { ...init, headers: { ...(init.headers ?? {}), 'X-CSRF-Token': csrfToken } }
}
