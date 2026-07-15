import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  ApiError,
  apiRequest,
  type ScreeningChatMessage,
  type ScreeningConversation,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ConfirmationDialog } from './ConfirmationDialog'

const errorCopy: Record<string, string> = {
  ASSISTANT_DISABLED: 'Conversational explanations are disabled. The canonical criterion explanations remain available below.',
  ASSISTANT_TIMEOUT: 'The explanation request timed out. Your message was not saved. Try again or use the canonical explanations.',
  ASSISTANT_RATE_LIMITED: 'The explanation provider is temporarily rate-limited. Your message was not saved; try again later.',
  ASSISTANT_PROVIDER_ERROR: 'The explanation provider is unavailable. Your message was not saved and the stored result is unchanged.',
  ASSISTANT_RESPONSE_INVALID: 'The provider response could not be safely grounded, so it was not saved.',
  ASSISTANT_MESSAGE_TOO_LONG: 'Keep the question within the displayed message limit.',
}

export function ScreeningChatPanel({ screeningId }: { screeningId: string }) {
  const { token } = useAuth()
  const [conversation, setConversation] = useState<ScreeningConversation | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [clearOpen, setClearOpen] = useState(false)
  const [clearing, setClearing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const loaded = await apiRequest<ScreeningConversation>(`/screenings/${screeningId}/conversation`, {}, token)
      if (!Array.isArray(loaded.messages) || !loaded.provider) throw new Error('Invalid conversation response')
      setConversation(loaded)
      setError('')
    } catch { setError('Conversation history could not be loaded. The saved criterion evidence is still available below.') }
    finally { setLoading(false) }
  }, [screeningId, token])
  useEffect(() => { void load() }, [load])

  const submit = async (event?: FormEvent, suggestedMessage?: string) => {
    event?.preventDefault()
    const current = (suggestedMessage ?? message).trim()
    if (!current || sending || !conversation?.provider.enabled) return
    setSending(true); setError('')
    try {
      const assistant = await apiRequest<ScreeningChatMessage>(
        `/screenings/${screeningId}/conversation/messages`,
        { method: 'POST', body: JSON.stringify({ message: current }) },
        token,
      )
      const userMessage: ScreeningChatMessage = {
        id: `pending-${Date.now()}`,
        role: 'user',
        content: current,
        answer_state: null,
        citations: [],
        provider: null,
        created_at: new Date().toISOString(),
        suggested_questions: [],
      }
      setConversation((existing) => existing ? {
        ...existing,
        messages: [...existing.messages, userMessage, assistant].slice(-existing.max_messages),
        suggested_questions: assistant.suggested_questions.length
          ? assistant.suggested_questions
          : existing.suggested_questions,
      } : existing)
      setMessage('')
    } catch (exception) {
      setError(exception instanceof ApiError
        ? errorCopy[exception.code] ?? exception.message
        : 'The explanation request failed. Your message was not saved.')
    } finally { setSending(false) }
  }

  const clear = async () => {
    setClearing(true); setError('')
    try {
      await apiRequest(`/screenings/${screeningId}/conversation`, { method: 'DELETE' }, token)
      setConversation((existing) => existing ? { ...existing, messages: [] } : existing)
      setClearOpen(false)
    } catch { setError('Conversation history could not be cleared. The screening result was not changed.') }
    finally { setClearing(false) }
  }

  const focusCitation = (evaluationId: string) => {
    const row = document.getElementById(`criterion-${evaluationId}`)
    row?.focus({ preventScroll: true })
  }

  return <section className="chat-panel" aria-labelledby="explain-result-title">
    <div className="chat-panel-head"><div><p className="eyebrow">Bounded explanation assistant</p><h2 id="explain-result-title">Explain this result</h2><p>Explains this stored educational result only. It cannot give medical advice, approve evidence, or change the outcome.</p></div>{conversation?.messages.length ? <button className="text-button danger" type="button" onClick={() => setClearOpen(true)}>Clear conversation</button> : null}</div>
    {loading ? <div className="chat-loading" aria-label="Loading conversation"><span /><span /><span /></div> : conversation ? <>
      {!conversation.provider.enabled && <div className="chat-system-state" role="status"><strong>Conversational assistant disabled</strong><span>Use the canonical explanations in the criterion table.</span></div>}
      {conversation.messages.length ? <ol className="chat-transcript" aria-live="polite">{conversation.messages.map((item) => <li className={`chat-message chat-${item.role} ${item.answer_state ? `chat-${item.answer_state}` : ''}`} key={item.id}><div className="chat-message-meta"><strong>{item.role === 'user' ? 'You' : item.answer_state === 'refused' ? 'Request declined' : item.answer_state === 'insufficient_evidence' ? 'Not enough evidence' : 'Result explanation'}</strong><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div><p>{item.content}</p>{item.citations.length > 0 && <div className="chat-citations" aria-label="Answer citations">{item.citations.map((citation) => <a href={`#criterion-${citation.evaluation_id}`} key={`${item.id}-${citation.evaluation_id}`} onClick={() => focusCitation(citation.evaluation_id)}>Criterion evidence · {citation.label}</a>)}</div>}</li>)}</ol> : <div className="chat-empty"><strong>Ask about the evidence already stored here</strong><p>Questions outside this screening, medical advice, and requests to change results are declined.</p></div>}
      <div className="suggested-prompts" aria-label="Suggested questions">{conversation.suggested_questions.map((prompt) => <button disabled={sending || !conversation.provider.enabled} type="button" key={prompt} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div>
      <form className="chat-composer" onSubmit={(event) => void submit(event)}><label htmlFor="screening-chat-message">Question about this stored result</label><div><textarea id="screening-chat-message" maxLength={conversation.max_message_chars} rows={3} disabled={sending || !conversation.provider.enabled} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask why a criterion passed, failed, or is unknown…" /><button className="primary-button" disabled={!message.trim() || sending || !conversation.provider.enabled} type="submit">{sending ? 'Checking evidence…' : 'Ask about result'}</button></div><small>Latest {conversation.max_messages} messages are retained. Previous chat is context only, never screening evidence.</small></form>
    </> : null}
    {error && <div className="form-error chat-error" role="alert">{error}<button className="text-button" type="button" onClick={() => void load()}>Reload conversation</button></div>}
    <ConfirmationDialog open={clearOpen} eyebrow="Conversation only" title="Clear this conversation?" confirmLabel="Clear conversation" busyLabel="Clearing…" busy={clearing} onCancel={() => setClearOpen(false)} onConfirm={() => void clear()}><p>This removes only the bounded chat history. The screening, evidence, canonical explanations, and review history remain unchanged.</p></ConfirmationDialog>
  </section>
}
