import { FormEvent, useEffect, useState } from 'react'

import { Operator, SendEmailRequest, supportApi, ThreadDetail, ThreadSummary } from './api'

type Tab = 'Email' | 'JSON'

function newId(prefix: string) {
  return `${prefix}-${crypto.randomUUID().slice(0, 20)}`
}

function statusLabel(status: ThreadSummary['status'] | ThreadDetail['status']) {
  if (status === 'approval_pending') return 'Awaiting administrative review'
  return status.replace('_', ' ')
}

function Compose({ thread, csrfToken, onSent, onExpired }: { thread: ThreadDetail | null; csrfToken: string; onSent: (detail: ThreadDetail | null, pending: boolean) => void; onExpired: () => void }) {
  const [fromEmail, setFromEmail] = useState('customer@example.test')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!fromEmail || !subject || !body) return setError('Email, subject, and message are required.')
    setSending(true)
    setError('')
    const request: SendEmailRequest = {
      thread_id: thread?.session_id ?? newId('THREAD'),
      message_id: newId('EMAIL'),
      from_email: fromEmail,
      subject,
      body,
    }
    try {
      const result = await supportApi.sendEmail(request, csrfToken)
      if (result.status === 'approval_pending') onSent(null, true)
      else onSent(result, false)
      setSubject('')
      setBody('')
    } catch (error) {
      if (isUnauthorized(error)) return onExpired()
      setError(errorMessage(error, 'Your simulated email could not be sent.'))
    } finally {
      setSending(false)
    }
  }

  return <form className="compose" onSubmit={submit}>
    <h2>{thread ? 'Reply' : 'Compose'}</h2>
    <p className="compose-explanation">{thread ? 'Reply continues the selected thread.' : 'Compose creates a new simulated customer thread.'}</p>
    <label>Email<input aria-label="Email" value={fromEmail} onChange={(event) => setFromEmail(event.target.value)} type="email" /></label>
    <label>Subject<input aria-label="Subject" value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
    <label>Message<textarea aria-label="Message" value={body} onChange={(event) => setBody(event.target.value)} /></label>
    {error && <p role="alert">{error}</p>}
    <button disabled={sending} type="submit">{sending ? 'Sending…' : 'Send simulated email'}</button>
  </form>
}

function Detail({ detail, csrfToken, onBack, onSent, onExpired }: { detail: ThreadDetail; csrfToken: string; onBack: () => void; onSent: (detail: ThreadDetail | null, pending: boolean) => void; onExpired: () => void }) {
  const [tab, setTab] = useState<Tab>('Email')
  const awaitingReview = detail.status === 'approval_pending'
  return <section className="detail" aria-label="Thread detail">
    <button className="back" onClick={onBack}>Back to inbox</button>
    <header><h1>{detail.messages[0]?.subject ?? 'Support conversation'}</h1><span className={`status ${detail.status}`}>{statusLabel(detail.status)}</span></header>
    {awaitingReview && <p className="pending" role="status">Awaiting administrative review. This thread is read-only.</p>}
    <div className="tabs" role="tablist">
      {(['Email', 'JSON'] as Tab[]).map((name) => <button key={name} role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{name}</button>)}
    </div>
    {tab === 'JSON' ? <pre>{JSON.stringify(detail, null, 2)}</pre> : <div className="messages">
      {detail.messages.map((message, index) => <article className={message.direction} key={`${message.message_id}-${index}`}>
        <strong>{message.from_email}</strong><span>{message.sent_at}</span><h2>{message.subject}</h2><p>{message.body}</p>
        {(message.category || message.issue_code || message.outcome) && <small>{[message.category, message.issue_code, message.outcome].filter(Boolean).join(' · ')}</small>}
      </article>)}
    </div>}
    {!awaitingReview && <Compose thread={detail} csrfToken={csrfToken} onSent={onSent} onExpired={onExpired} />}
  </section>
}

function errorMessage(error: unknown, fallback: string): string {
  const kind = (error as { kind?: string } | null)?.kind
  if (!kind || !['unauthorized', 'forbidden', 'rate_limited', 'gateway', 'request'].includes(kind)) return fallback
  return {
    unauthorized: 'Your session expired. Please sign in again.',
    forbidden: 'You are not allowed to use Support Inbox.',
    rate_limited: 'Too many requests. Please try again later.',
    gateway: 'Support service is temporarily unavailable.',
    request: fallback,
  }[kind as 'unauthorized' | 'forbidden' | 'rate_limited' | 'gateway' | 'request']
}

function isUnauthorized(error: unknown): boolean {
  return (error as { kind?: string } | null)?.kind === 'unauthorized'
}

function Login({ error, onLogin }: { error: string; onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    try { await onLogin(username, password) } finally { setPassword(''); setSubmitting(false) }
  }
  return <main className="login"><form onSubmit={submit}>
    <h1>Sign in to Support Inbox</h1>
    {error && <p role="alert">{error}</p>}
    <label>Username<input aria-label="Username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
    <label>Password<input aria-label="Password" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
    <button disabled={submitting} type="submit">{submitting ? 'Signing in…' : 'Sign in'}</button>
  </form></main>
}

export default function App() {
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [detail, setDetail] = useState<ThreadDetail | null>(null)
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [operator, setOperator] = useState<Operator | null>(null)
  const [csrfToken, setCsrfToken] = useState('')
  const [error, setError] = useState('')
  const [inboxError, setInboxError] = useState('')
  const [detailError, setDetailError] = useState('')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    supportApi.getSession().then(({ operator: restored, csrf_token }) => {
      setOperator(restored); setCsrfToken(csrf_token)
      return loadInbox()
    }).catch((reason: unknown) => {
      if (isUnauthorized(reason)) return
      setError(errorMessage(reason, 'The inbox could not be loaded.'))
    }).finally(() => setLoading(false))
  }, [])

  function expired() {
    setOperator(null); setCsrfToken(''); setThreads([]); setDetail(null); setSelectedThreadId(null)
    setInboxError(''); setDetailError(''); setError('Your session expired. Please sign in again.')
  }

  async function loadInbox() {
    try {
      setInboxError('')
      setThreads((await supportApi.listThreads()).threads)
    } catch (reason) {
      if (isUnauthorized(reason)) expired()
      else setInboxError(errorMessage(reason, 'The inbox could not be loaded.'))
    }
  }

  async function loadDetail(sessionId: string) {
    try {
      setDetailError('')
      setDetail(await supportApi.getThread(sessionId))
      setPending(false)
    } catch (reason) {
      if (isUnauthorized(reason)) expired()
      else setDetailError(errorMessage(reason, 'This thread could not be loaded.'))
    }
  }

  async function login(username: string, password: string) {
    try {
      const result = await supportApi.login(username, password)
      setOperator(result.operator); setCsrfToken(result.csrf_token); setError('')
      setLoading(true)
      await loadInbox()
    } catch (reason) {
      setError(isUnauthorized(reason) ? 'Invalid username or password.' : errorMessage(reason, 'Invalid username or password.'))
    } finally { setLoading(false) }
  }

  async function logout() {
    try { await supportApi.logout(csrfToken) } catch { /* The local session is cleared even if the network is unavailable. */ }
    expired(); setLoading(false)
  }

  async function selectThread(sessionId: string) {
    setSelectedThreadId(sessionId)
    setDetail(null)
    setPending(false)
    await loadDetail(sessionId)
  }

  async function refresh() {
    setLoading(true)
    await Promise.all([loadInbox(), selectedThreadId ? loadDetail(selectedThreadId) : Promise.resolve()])
    setLoading(false)
  }

  async function sent(result: ThreadDetail | null, isPending: boolean) {
    setPending(isPending)
    if (result) {
      setDetail(result)
      setSelectedThreadId(result.session_id)
      setDetailError('')
    }
    await loadInbox()
  }

  if (loading && !operator) return <main aria-busy="true"><p role="status">Checking session…</p></main>
  if (!operator) return <Login error={error} onLogin={login} />
  return <main className={selectedThreadId ? 'inbox selected' : 'inbox'}>
    <aside className="thread-list" aria-label="Support threads">
      <header><h1>Support Inbox</h1><p>Signed in as {operator.display_name}</p><div className="header-actions"><button onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh inbox and selected thread'}</button><button onClick={logout}>Sign out</button></div></header>
      <section className="demo-guide" aria-label="Recruiter demo guide"><strong>How this demo works</strong><p>Customer Support routes requests to Order Support, Product Support, and Returns &amp; Refunds Support.</p><p>Compose creates a new simulated customer thread; Reply continues the selected thread.</p></section>
      {loading && <p role="status">Loading threads…</p>}
      {inboxError && <div className="load-error"><p role="alert">{inboxError}</p><button onClick={loadInbox}>Retry inbox</button></div>}
      {!loading && !threads.length && <p>No safely mappable support threads yet.</p>}
      {threads.map((thread) => <button className="thread" key={thread.session_id} onClick={() => selectThread(thread.session_id)}>
        <strong>{thread.subject}</strong><span>{thread.customer_email}</span><p>{thread.preview}</p><small>{statusLabel(thread.status)}</small>
      </button>)}
      <Compose thread={null} csrfToken={csrfToken} onSent={sent} onExpired={expired} />
    </aside>
    <section className="panel">
      {pending && <p className="pending" role="status">Awaiting administrative review.</p>}
      {detailError && <div className="load-error detail-error"><p role="alert">{detailError}</p>{selectedThreadId && <button onClick={() => loadDetail(selectedThreadId)}>Retry thread</button>}</div>}
      {detail ? <Detail detail={detail} csrfToken={csrfToken} onBack={() => { setDetail(null); setSelectedThreadId(null); setDetailError('') }} onSent={sent} onExpired={expired} /> : !detailError && <div className="empty"><h2>Select a thread</h2><p>Choose a conversation to inspect its safely normalized emails.</p></div>}
    </section>
  </main>
}
