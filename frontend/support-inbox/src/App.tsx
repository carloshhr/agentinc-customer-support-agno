import { FormEvent, useEffect, useState } from 'react'

import { SendEmailRequest, supportApi, ThreadDetail, ThreadSummary } from './api'

type Tab = 'Email' | 'JSON'

function newId(prefix: string) {
  return `${prefix}-${crypto.randomUUID().slice(0, 20)}`
}

function Compose({ thread, onSent }: { thread: ThreadDetail | null; onSent: (detail: ThreadDetail | null, pending: boolean) => void }) {
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
      const result = await supportApi.sendEmail(request)
      if (result.status === 'approval_pending') onSent(null, true)
      else onSent(result, false)
      setSubject('')
      setBody('')
    } catch {
      setError('Your simulated email could not be sent.')
    } finally {
      setSending(false)
    }
  }

  return <form className="compose" onSubmit={submit}>
    <h2>{thread ? 'Reply' : 'Compose'}</h2>
    <label>Email<input aria-label="Email" value={fromEmail} onChange={(event) => setFromEmail(event.target.value)} type="email" /></label>
    <label>Subject<input aria-label="Subject" value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
    <label>Message<textarea aria-label="Message" value={body} onChange={(event) => setBody(event.target.value)} /></label>
    {error && <p role="alert">{error}</p>}
    <button disabled={sending} type="submit">{sending ? 'Sending…' : 'Send simulated email'}</button>
  </form>
}

function Detail({ detail, onBack, onSent }: { detail: ThreadDetail; onBack: () => void; onSent: (detail: ThreadDetail | null, pending: boolean) => void }) {
  const [tab, setTab] = useState<Tab>('Email')
  return <section className="detail" aria-label="Thread detail">
    <button className="back" onClick={onBack}>Back to inbox</button>
    <header><h1>{detail.messages[0]?.subject ?? 'Support conversation'}</h1><span className={`status ${detail.status}`}>{detail.status.replace('_', ' ')}</span></header>
    <div className="tabs" role="tablist">
      {(['Email', 'JSON'] as Tab[]).map((name) => <button key={name} role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{name}</button>)}
    </div>
    {tab === 'JSON' ? <pre>{JSON.stringify(detail, null, 2)}</pre> : <div className="messages">
      {detail.messages.map((message, index) => <article className={message.direction} key={`${message.message_id}-${index}`}>
        <strong>{message.from_email}</strong><span>{message.sent_at}</span><h2>{message.subject}</h2><p>{message.body}</p>
        {(message.category || message.issue_code || message.outcome) && <small>{[message.category, message.issue_code, message.outcome].filter(Boolean).join(' · ')}</small>}
      </article>)}
    </div>}
    <Compose thread={detail} onSent={onSent} />
  </section>
}

export default function App() {
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [detail, setDetail] = useState<ThreadDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    supportApi.listThreads().then(({ threads: loaded }) => setThreads(loaded)).catch(() => setError('The inbox could not be loaded.')).finally(() => setLoading(false))
  }, [])

  async function selectThread(sessionId: string) {
    try {
      setError('')
      setDetail(await supportApi.getThread(sessionId))
      setPending(false)
    } catch { setError('This thread could not be loaded.') }
  }

  async function sent(result: ThreadDetail | null, isPending: boolean) {
    setPending(isPending)
    if (result) setDetail(result)
    try { setThreads((await supportApi.listThreads()).threads) } catch { setError('The inbox was sent, but could not be refreshed.') }
  }

  return <main className={detail ? 'inbox selected' : 'inbox'}>
    <aside className="thread-list" aria-label="Support threads">
      <header><h1>Support Inbox</h1><p>Simulated customer email</p></header>
       {loading && <p role="status">Loading threads…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !threads.length && <p>No safely mappable support threads yet.</p>}
      {threads.map((thread) => <button className="thread" key={thread.session_id} onClick={() => selectThread(thread.session_id)}>
        <strong>{thread.subject}</strong><span>{thread.customer_email}</span><p>{thread.preview}</p><small>{thread.status.replace('_', ' ')}</small>
      </button>)}
      <Compose thread={null} onSent={sent} />
    </aside>
    <section className="panel">
      {pending && <p className="pending" role="status">This request is pending administrative review.</p>}
      {detail ? <Detail detail={detail} onBack={() => setDetail(null)} onSent={sent} /> : <div className="empty"><h2>Select a thread</h2><p>Choose a conversation to inspect its safely normalized emails.</p></div>}
    </section>
  </main>
}
