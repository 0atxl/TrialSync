import type { Fact, PatientFactCatalogEntry, PatientFactGroup } from '../api/client'

export const clinicalGroupLabels: Record<PatientFactGroup, string> = {
  conditions: 'Conditions',
  medications: 'Medications',
  observations: 'Labs and observations',
}

export function factLabel(fact: Fact) {
  return fact.concept
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function factCatalogEntry(entries: PatientFactCatalogEntry[], fact: Fact) {
  return entries.find(
    (entry) => entry.fact_type === fact.fact_type && entry.concept === fact.concept,
  )
}

function assertionLabel(fact: Fact, entry?: PatientFactCatalogEntry) {
  if (entry?.input_kind === 'pregnancy_status') {
    if (fact.assertion === 'present') return 'Pregnant'
    if (fact.assertion === 'absent') return 'Not pregnant'
    return 'Unknown'
  }
  return fact.assertion.charAt(0).toUpperCase() + fact.assertion.slice(1)
}

function measurementLabel(fact: Fact) {
  if (fact.assertion === 'unknown') return 'Unknown'
  if (fact.value_numeric === null) return assertionLabel(fact)
  const parsedValue = Number(fact.value_numeric)
  const value = Number.isFinite(parsedValue) ? String(parsedValue) : fact.value_numeric
  const separator = fact.unit === '%' ? '' : ' '
  return `${value}${fact.unit ? `${separator}${fact.unit}` : ''}`
}

export function clinicalValueLabel(fact: Fact, entry?: PatientFactCatalogEntry) {
  return entry?.input_kind === 'numeric'
    ? measurementLabel(fact)
    : assertionLabel(fact, entry)
}
