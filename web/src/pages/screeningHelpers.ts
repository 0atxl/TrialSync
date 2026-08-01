import type { ScreeningState, Trial, TrialVersion } from '../api/client'

export const stateLabel = (state: ScreeningState) => state.replaceAll('_', ' ')
const reasonLabels: Record<string, string> = {
  MISSING_FACT: 'Required information is not recorded.',
  EVALUATED_TRUE: 'The recorded evidence satisfies this rule.',
  EVALUATED_FALSE: 'The recorded evidence does not satisfy this rule.',
  UNSUPPORTED_RULE: 'This rule needs manual review because it is not supported yet.',
  CONFLICTING_EVIDENCE: 'The record contains conflicting evidence.',
  INCOMPATIBLE_UNIT: 'The recorded unit cannot be compared safely.',
  STALE_EVIDENCE: 'The available evidence is outside the required time window.',
  INVALID_RULE: 'This rule is invalid and requires manual correction.',
}
export const reasonLabel = (reason: string) => reasonLabels[reason] ?? 'This criterion requires review of its recorded evidence.'
export const screeningTrialLabel = (screening: { trial_version?: { registry_id: string; title: string; version: number }; trial_version_id: string }, trials: Trial[] = []) => screening.trial_version ? `${screening.trial_version.registry_id} · ${screening.trial_version.title}` : versionLabel(trials, screening.trial_version_id)
export const versionLabel = (trials: Trial[], id: string) => {
  for (const trial of trials) {
    const version = trial.versions.find((item) => item.id === id)
    if (version) return `${trial.registry_id} · ${trial.title}`
  }
  return `Protocol ${id.slice(0, 8)}`
}
export const approvedVersions = (trials: Trial[]): Array<{ trial: Trial; version: TrialVersion }> =>
  trials.flatMap((trial) => {
    const version = trial.versions.filter((item) => item.status === 'approved').at(-1)
    return version ? [{ trial, version }] : []
  })
