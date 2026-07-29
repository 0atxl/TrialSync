import { useCallback, useMemo, useRef, useState } from 'react'

export type MutationStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'failed'

export function useMutationState() {
  const [status, setStatus] = useState<MutationStatus>('idle')
  const inFlight = useRef(false)

  const markDirty = useCallback(() => {
    setStatus((current) => (current === 'saving' ? current : 'dirty'))
  }, [])
  const setDirty = useCallback((dirty: boolean) => {
    setStatus((current) => {
      if (current === 'saving') return current
      return dirty ? 'dirty' : 'idle'
    })
  }, [])
  const start = useCallback(() => {
    if (inFlight.current) return false
    inFlight.current = true
    setStatus('saving')
    return true
  }, [])
  const succeed = useCallback(() => {
    inFlight.current = false
    setStatus('saved')
  }, [])
  const fail = useCallback(() => {
    inFlight.current = false
    setStatus('failed')
  }, [])
  const reset = useCallback(() => {
    inFlight.current = false
    setStatus('idle')
  }, [])

  return useMemo(
    () => ({
      status,
      isSaving: status === 'saving',
      hasUnsavedChanges: status === 'dirty' || status === 'failed',
      markDirty,
      setDirty,
      start,
      succeed,
      fail,
      reset,
    }),
    [fail, markDirty, reset, setDirty, start, status, succeed],
  )
}
