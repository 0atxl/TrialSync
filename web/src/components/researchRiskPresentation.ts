export const baselineFields = [
  { name: 'site_region', label: 'Site region', kind: 'select', options: ['central', 'north', 'south', 'east', 'west'] },
  { name: 'treatment_arm', label: 'Treatment arm', kind: 'select', options: ['active', 'control'] },
  { name: 'baseline_functional_severity', label: 'Baseline functional severity', kind: 'number', min: 0, max: 1, step: 0.01, hint: 'Score from 0 to 1' },
  { name: 'patient_reported_burden', label: 'Patient-reported burden', kind: 'number', min: 0, max: 1, step: 0.01, hint: 'Score from 0 to 1' },
  { name: 'baseline_treatment_burden', label: 'Treatment burden', kind: 'number', min: 0, max: 20, step: 1, hint: 'Score from 0 to 20' },
  { name: 'travel_access_burden', label: 'Travel and access burden', kind: 'number', min: 0, max: 4, step: 1, hint: 'Score from 0 to 4' },
  { name: 'support_availability', label: 'Available support', kind: 'number', min: 0, max: 4, step: 1, hint: 'Score from 0 to 4' },
] as const

export const featureLabels: Record<string, string> = {
  condition_category: 'Condition category',
  site_region: 'Site region',
  treatment_arm: 'Treatment arm',
  age: 'Age at screening',
  sex: 'Recorded sex',
  baseline_functional_severity: 'Baseline functional severity',
  patient_reported_burden: 'Patient-reported burden',
  baseline_comorbidity_burden: 'Recorded condition burden',
  baseline_treatment_burden: 'Treatment burden',
  travel_access_burden: 'Travel and access burden',
  support_availability: 'Available support',
  medication_count: 'Recorded medications',
  latest_functional_severity: 'Latest functional severity',
  functional_severity_slope: 'Change in functional severity',
  functional_observation_count: 'Functional assessments',
  missed_dose_rate: 'Missed doses',
  delayed_visit_count: 'Delayed visits',
  missed_visit_rate: 'Missed visits',
  mean_visit_delay_days: 'Visit delay',
  measurement_missingness_rate: 'Missing assessments',
  adverse_event_count: 'Adverse events',
  adverse_event_burden: 'Adverse-event burden',
}

export function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function numeric(value: FormDataEntryValue | null) {
  return Number(String(value ?? ''))
}

export function displayFeatureValue(value: string | number | null) {
  if (value == null) return 'Missing'
  if (typeof value === 'number' && !Number.isInteger(value)) {
    return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
  }
  return String(value).replaceAll('_', ' ')
}
