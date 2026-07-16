import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

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

const retryableErrors = new Set([
  'ASSISTANT_TIMEOUT',
  'ASSISTANT_RATE_LIMITED',
  'ASSISTANT_PROVIDER_ERROR',
  'ASSISTANT_RESPONSE_INVALID',
])

export function ScreeningChatPanel({ screeningId }: { screeningId: string }) {
  const { token } = useAuth()
  const [conversation, setConversation] = useState<ScreeningConversation | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [retryMessage, setRetryMessage] = useState('')
  const [announcement, setAnnouncement] = useState({ id: 0, text: '' })
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [pendingMessage, setPendingMessage] = useState<ScreeningChatMessage | null>(null)
  const [clearOpen, setClearOpen] = useState(false)
  const [clearing, setClearing] = useState(false)
  const transcriptRef = useRef<HTMLOListElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const restoreFocusRef = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const loaded = await apiRequest<ScreeningConversation>(`/screenings/${screeningId}/conversation`, {}, token)
      if (!Array.isArray(loaded.messages) || !loaded.provider) throw new Error('Invalid conversation response')
      setConversation(loaded)
      setError('')
      setRetryMessage('')
    } catch { setError('Conversation history could not be loaded. The saved criterion evidence is still available below.') }
    finally { setLoading(false) }
  }, [screeningId, token])
  useEffect(() => { void load() }, [load])
  useLayoutEffect(() => {
    const transcript = transcriptRef.current
    if (transcript) transcript.scrollTop = transcript.scrollHeight
  }, [conversation?.messages, pendingMessage, sending])
  useEffect(() => {
    if (!sending && restoreFocusRef.current) {
      restoreFocusRef.current = false
      composerRef.current?.focus({ preventScroll: true })
    }
  }, [sending])

  const announce = (text: string) => setAnnouncement((current) => ({
    id: current.id + 1,
    text,
  }))

  const submit = async (event?: FormEvent, suggestedMessage?: string) => {
    event?.preventDefault()
    const current = (suggestedMessage ?? message).trim()
    if (!current || sending || !conversation?.provider.enabled) return
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
    setPendingMessage(userMessage)
    setMessage('')
    setSending(true); setError(''); setRetryMessage('')
    try {
      const assistant = await apiRequest<ScreeningChatMessage>(
        `/screenings/${screeningId}/conversation/messages`,
        { method: 'POST', body: JSON.stringify({ message: current }) },
        token,
      )
      setConversation((existing) => existing ? {
        ...existing,
        messages: [...existing.messages, userMessage, assistant].slice(-existing.max_messages),
        suggested_questions: assistant.suggested_questions.length
          ? assistant.suggested_questions
          : existing.suggested_questions,
      } : existing)
      setMessage('')
      announce(assistant.answer_state === 'refused'
        ? 'The result assistant declined the request.'
        : assistant.answer_state === 'insufficient_evidence'
          ? 'The result assistant found insufficient stored evidence.'
          : 'A new result explanation is ready.')
    } catch (exception) {
      setMessage(current)
      if (exception instanceof ApiError) {
        setError(errorCopy[exception.code] ?? exception.message)
        if (retryableErrors.has(exception.code)) setRetryMessage(current)
      } else {
        setError('The connection ended before the save status could be confirmed. Reload the conversation before trying again.')
      }
    } finally {
      setPendingMessage(null)
      restoreFocusRef.current = true
      setSending(false)
    }
  }

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  const clear = async () => {
    setClearing(true); setError('')
    try {
      await apiRequest(`/screenings/${screeningId}/conversation`, { method: 'DELETE' }, token)
      setConversation((existing) => existing ? { ...existing, messages: [] } : existing)
      setClearOpen(false)
      announce('Conversation cleared. The screening result is unchanged.')
    } catch { setError('Conversation history could not be cleared. The screening result was not changed.') }
    finally { setClearing(false) }
  }

  const focusCitation = (evaluationId: string) => {
    const row = document.getElementById(`criterion-${evaluationId}`)
    row?.focus({ preventScroll: true })
  }

  const renderMessage = (item: ScreeningChatMessage) => <li className={`chat-message chat-${item.role} ${item.answer_state ? `chat-${item.answer_state}` : ''}`} key={item.id}>
    <div className="chat-message-meta"><strong>{item.role === 'user' ? 'You' : item.answer_state === 'refused' ? 'Request declined' : item.answer_state === 'insufficient_evidence' ? 'Not enough evidence' : 'Result explanation'}</strong><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div>
    <p>{item.content}</p>
    {item.citations.length > 0 && <div className="chat-citations" aria-label="Answer citations">{item.citations.map((citation) => <a href={`#criterion-${citation.evaluation_id}`} key={`${item.id}-${citation.evaluation_id}`} onClick={() => focusCitation(citation.evaluation_id)}>Criterion evidence · {citation.label}</a>)}</div>}
  </li>

  return <section className="chat-panel" id="screening-chat-panel" tabIndex={-1} aria-labelledby="explain-result-title">
    <div className="chat-panel-head"><div><p className="eyebrow">Result assistant</p><h2 id="explain-result-title">Ask about this result</h2><p>Explore the criteria, recorded evidence, and any information that still needs follow-up.</p></div>{conversation?.messages.length ? <button className="text-button danger" type="button" onClick={() => setClearOpen(true)}>Clear conversation</button> : null}</div>
    {loading ? <div className="chat-loading" aria-label="Loading conversation"><span /><span /><span /></div> : conversation ? <>
      {!conversation.provider.enabled && <div className="chat-system-state" role="status"><strong>Conversational assistant disabled</strong><span>Use the canonical explanations in the criterion table.</span></div>}
      <ol className="chat-transcript" ref={transcriptRef} aria-busy={sending}>
        {!conversation.messages.length && !pendingMessage ? <li className="chat-empty"><strong>What would you like to understand?</strong><p>Ask why criteria passed or failed, what evidence was used, or what information is still needed.</p></li> : null}
        {conversation.messages.map(renderMessage)}
        {pendingMessage ? renderMessage(pendingMessage) : null}
        {sending ? <li className="chat-message chat-assistant chat-typing" role="status"><span className="visually-hidden">The result assistant is preparing a response.</span><span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" /></li> : null}
      </ol>
      <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true" key={announcement.id}>{announcement.text}</div>
      <div className={`suggested-prompts suggested-prompts-${Math.min(conversation.suggested_questions.length, 3)}`} aria-label="Suggested questions">{conversation.suggested_questions.map((prompt) => <button disabled={sending || !conversation.provider.enabled} type="button" key={prompt} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div>
      <form className="chat-composer" onSubmit={(event) => void submit(event)}><div className="chat-composer-label"><label htmlFor="screening-chat-message">Question about this stored result</label><small>{message.length} / {conversation.max_message_chars} · Enter sends · Shift+Enter adds a line</small></div><div><textarea ref={composerRef} id="screening-chat-message" maxLength={conversation.max_message_chars} rows={2} disabled={sending || !conversation.provider.enabled} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="What would you like to understand?" /><button className="primary-button" disabled={!message.trim() || sending || !conversation.provider.enabled} type="submit">{sending ? 'Responding…' : 'Send question'}</button></div></form>
    </> : null}
    {error && <div className="form-error chat-error chat-error-toast" role="alert"><span>{error}</span><div>{retryMessage ? <button className="text-button" type="button" onClick={() => void submit(undefined, retryMessage)}>Retry question</button> : null}<button className="text-button" type="button" onClick={() => void load()}>Reload conversation</button><button className="text-button" type="button" aria-label="Dismiss chat error" onClick={() => { setError(''); setRetryMessage('') }}>Dismiss</button></div></div>}
    <ConfirmationDialog open={clearOpen} eyebrow="Conversation only" title="Clear this conversation?" confirmLabel="Clear conversation" busyLabel="Clearing…" busy={clearing} onCancel={() => setClearOpen(false)} onConfirm={() => void clear()}><p>This removes only the bounded chat history. The screening, evidence, canonical explanations, and review history remain unchanged.</p></ConfirmationDialog>
  </section>
}
