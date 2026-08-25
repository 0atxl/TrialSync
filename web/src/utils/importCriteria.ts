import { type PatientFactCatalogEntry, type TrialImportCriterion } from '../api/client'

export function importedCriterionIsReady(
  criterion: TrialImportCriterion,
  catalog: PatientFactCatalogEntry[],
) {
  const rule = criterion.normalized_rule
  if (!rule) return false
  if (rule.op === 'concept_is') {
    return rule.fact_type === 'demographic'
      && ['female', 'male'].includes(String(rule.concept))
  }
  if (typeof rule.fact !== 'string') return false
  const entry = catalog.find((item) =>
    `${item.fact_type}.${item.concept}` === rule.fact,
  )
  const subjectIsKnown = rule.fact === 'demographic.age'
    || Boolean(entry?.screening_supported)
  if (!subjectIsKnown) return false
  const hasNumber = (value: unknown) =>
    value !== ''
    && value !== null
    && value !== undefined
    && Number.isFinite(Number(value))
  if (rule.op === 'between') {
    return hasNumber(rule.min)
      && hasNumber(rule.max)
      && Number(rule.min) <= Number(rule.max)
  }
  if (rule.op === 'gte' || rule.op === 'lte') return hasNumber(rule.value)
  return rule.op === 'present' || rule.op === 'absent'
}

export function countUnresolvedCriteria(
  criteria: TrialImportCriterion[],
  catalog: PatientFactCatalogEntry[],
) {
  return criteria.filter((criterion) =>
    criterion.selected && !importedCriterionIsReady(criterion, catalog),
  ).length
}
