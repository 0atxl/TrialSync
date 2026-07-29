import type { BiologicalSex } from '../api/client'

type BiologicalSexFieldProps = {
  value: BiologicalSex | null | undefined
  onChange: (value: BiologicalSex | null) => void
  name?: string
  invalidMessage?: string
}

export function BiologicalSexField({
  value,
  onChange,
  name = 'sex',
  invalidMessage,
}: BiologicalSexFieldProps) {
  return (
    <fieldset className="sex-field" aria-describedby={invalidMessage ? `${name}-error` : undefined}>
      <legend>Biological sex for screening</legend>
      <div className="sex-options">
        {(['female', 'male'] as const).map((option) => (
          <label className={value === option ? 'sex-option selected' : 'sex-option'} key={option}>
            <input
              checked={value === option}
              name={name}
              type="radio"
              value={option}
              onChange={() => onChange(option)}
            />
            <span>{option === 'female' ? 'Female' : 'Male'}</span>
          </label>
        ))}
        <button
          className={value === null ? 'not-recorded-button selected' : 'not-recorded-button'}
          type="button"
          aria-pressed={value === null}
          onClick={() => onChange(null)}
        >
          Not recorded
        </button>
      </div>
      <small>Used only by supported deterministic screening criteria.</small>
      {invalidMessage ? <span className="field-error" id={`${name}-error`} role="alert">{invalidMessage}</span> : null}
    </fieldset>
  )
}
