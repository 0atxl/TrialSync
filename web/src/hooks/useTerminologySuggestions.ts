import { useEffect, useState } from 'react'

import {
  apiRequest,
  type PatientFactCatalogSuggestionResponse,
  type PatientFactGroup,
  type PatientUnsupportedDetailCategory,
  type TerminologySuggestion,
} from '../api/client'

export type TerminologyScope = PatientFactGroup | 'all' | 'demographics'

const factTypeByScope: Partial<Record<TerminologyScope, string>> = {
  conditions: 'condition',
  medications: 'medication',
  observations: 'observation',
}

export function suggestionCategory(
  suggestion: TerminologySuggestion,
): PatientUnsupportedDetailCategory {
  if (suggestion.source === 'conditions') return 'condition'
  if (suggestion.source === 'rxnorm') return 'medication'
  return 'observation'
}

export function suggestionSourceLabel(suggestion: TerminologySuggestion) {
  if (suggestion.source === 'conditions') return 'Condition'
  if (suggestion.source === 'rxnorm') return 'Medication'
  return 'Lab or observation'
}

export function useTerminologySuggestions(
  query: string,
  scope: TerminologyScope,
  token: string | null,
) {
  const [suggestions, setSuggestions] = useState<TerminologySuggestion[]>([])
  const [suggesting, setSuggesting] = useState(false)
  const [suggestionNotice, setSuggestionNotice] = useState('')

  useEffect(() => {
    const term = query.trim()
    if (term.length < 2 || scope === 'demographics') {
      setSuggestions([])
      setSuggestionNotice('')
      setSuggesting(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setSuggesting(true)
      try {
        const factType = factTypeByScope[scope]
        const response = await apiRequest<PatientFactCatalogSuggestionResponse>(
          `/patient-fact-catalog/suggestions?query=${encodeURIComponent(term)}${factType ? `&fact_type=${factType}` : ''}`,
          { signal: controller.signal },
          token,
        )
        setSuggestions(response.suggestions)
        setSuggestionNotice(
          response.unavailable_sources.length
            ? 'Some live suggestions are unavailable. Supported matches still work.'
            : '',
        )
      } catch {
        if (!controller.signal.aborted) {
          setSuggestions([])
          setSuggestionNotice('Live suggestions are unavailable. Supported matches still work.')
        }
      } finally {
        if (!controller.signal.aborted) setSuggesting(false)
      }
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, scope, token])

  return { suggestions, suggesting, suggestionNotice }
}
