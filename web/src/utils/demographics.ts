import type { BiologicalSex } from '../api/client'

export function parseBiologicalSex(
  value: string | null | undefined,
): BiologicalSex | null | undefined {
  if (value?.trim().toLowerCase() === 'male') return 'male'
  if (value?.trim().toLowerCase() === 'female') return 'female'
  return value === null || value === undefined || value.trim() === '' ? null : undefined
}

export function biologicalSexLabel(value: string | null | undefined) {
  const canonical = parseBiologicalSex(value)
  if (canonical === 'male') return 'Male'
  if (canonical === 'female') return 'Female'
  return canonical === null ? 'Not recorded' : 'Needs review'
}
