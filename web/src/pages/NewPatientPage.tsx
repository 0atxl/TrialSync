import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, apiRequest, type BiologicalSex, type Patient } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BiologicalSexField } from '../components/BiologicalSexField'
import { useToast } from '../components/ToastProvider'
import { UnsavedChangesDialog } from '../components/UnsavedChangesDialog'
import { useMutationState } from '../hooks/useMutationState'
import { useUnsavedChanges } from '../hooks/useUnsavedChanges'
import { isFutureIsoDate, todayIsoDate } from '../utils/dates'

type PatientValues = {
  display_name: string
  date_of_birth: string
  sex: BiologicalSex | null
}

const EMPTY_PATIENT: PatientValues = {
  display_name: '',
  date_of_birth: '',
  sex: null,
}

export function NewPatientPage() {
  const { token } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [pending, setPending] = useState<PatientValues | null>(null)
  const [values, setValues] = useState(EMPTY_PATIENT)
  const mutation = useMutationState()
  const unsavedChanges = useUnsavedChanges(mutation.hasUnsavedChanges)
  useEffect(() => {
    const dialog = dialogRef.current
    if (pending && dialog && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
    }
    if (!pending && dialog?.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [pending])

  const updateValue = <Key extends keyof PatientValues>(key: Key, value: PatientValues[Key]) => {
    setValues((current) => {
      const updated = { ...current, [key]: value }
      mutation.setDirty(
        updated.display_name.trim() !== '' ||
          updated.date_of_birth !== '' ||
          updated.sex !== null,
      )
      return updated
    })
    setFieldError('')
  }

  const create = async (values: PatientValues, confirm = false) => {
    if (isFutureIsoDate(values.date_of_birth)) {
      setFieldError('Date of birth cannot be in the future.')
      return
    }
    if (!mutation.start()) return
    setError('')
    setFieldError('')
    try {
      const patient = await apiRequest<Patient>(
        '/patients',
        {
          method: 'POST',
          body: JSON.stringify({
            display_name: values.display_name,
            date_of_birth: values.date_of_birth || null,
            sex: values.sex,
            confirm_duplicate_name: confirm,
          }),
        },
        token,
      )
      mutation.succeed()
      showToast({
        variant: 'success',
        title: 'Patient created',
        message: `${patient.display_name} is ready for structured clinical details.`,
      })
      unsavedChanges.allowNextNavigation()
      navigate(`/patients/${patient.id}`)
    } catch (exception) {
      mutation.fail()
      if (exception instanceof ApiError && exception.code === 'PATIENT_NAME_REVIEW_REQUIRED') {
        setPending(values)
        setError('A patient with this name already exists. Review it or continue only if this is a distinct person.')
      } else if (
        exception instanceof ApiError &&
        exception.code === 'PATIENT_DOB_IN_FUTURE'
      ) {
        setFieldError('Date of birth cannot be in the future.')
      } else {
        const message = 'The patient could not be created. Your entered values are still here.'
        setError(message)
        showToast({
          variant: 'error',
          title: 'Patient not created',
          message,
          announce: false,
        })
      }
    }
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void create(values)
  }

  return (
    <section className="route-entry workspace-page form-page">
      <Link className="back-link" to="/patients">← Patients</Link>
      <header className="page-heading">
        <div>
          <p className="eyebrow">New record</p>
          <h1>Add a patient</h1>
          <p>TrialSync generates a record ID. Add structured facts after saving the profile.</p>
        </div>
      </header>
      <form
        className="creation-form"
        noValidate
        onSubmit={submit}
      >
        <div className="form-section">
          <h2>Patient profile</h2>
          <div className="form-grid">
            <label>
              Display name
              <input
                name="display_name"
                required
                autoFocus
                placeholder="Patient name"
                value={values.display_name}
                onChange={(event) => updateValue('display_name', event.target.value)}
              />
            </label>
            <label>
              Date of birth
              <input
                aria-describedby={fieldError ? 'new-patient-dob-error' : undefined}
                max={todayIsoDate()}
                name="date_of_birth"
                type="date"
                value={values.date_of_birth}
                onChange={(event) => updateValue('date_of_birth', event.target.value)}
              />
              {fieldError ? <span className="field-error" id="new-patient-dob-error" role="alert">{fieldError}</span> : null}
            </label>
            <BiologicalSexField
              value={values.sex}
              onChange={(value) => updateValue('sex', value)}
            />
          </div>
        </div>
        <div className="data-boundary">
          <strong>Data boundary</strong>
          <span>Do not enter real patient information.</span>
        </div>
        {error && !pending ? <div className="form-error" role="alert">{error}</div> : null}
        <div className="form-actions">
          <Link className="secondary-button" to="/patients">Cancel</Link>
          <button
            className="primary-button"
            disabled={mutation.isSaving || !mutation.hasUnsavedChanges}
            type="submit"
          >
            {mutation.isSaving ? 'Creating…' : 'Create patient'}
          </button>
        </div>
        <dialog
          ref={dialogRef}
          className="confirmation-dialog"
          aria-labelledby="duplicate-patient-title"
          aria-describedby="duplicate-patient-copy"
          onCancel={() => {
            setPending(null)
            setError('')
          }}
        >
          <p className="eyebrow">Possible duplicate</p>
          <h2 id="duplicate-patient-title">Review this patient name</h2>
          <p id="duplicate-patient-copy">{error}</p>
          <div className="warning-actions">
            <Link
              className="secondary-button"
              to="/patients"
              onClick={unsavedChanges.allowNextNavigation}
            >
              Review existing records
            </Link>
            <button
              autoFocus
              className="primary-button"
              disabled={mutation.isSaving}
              type="button"
              onClick={() => pending && void create(pending, true)}
            >
              {mutation.isSaving ? 'Creating…' : 'Create distinct patient'}
            </button>
          </div>
        </dialog>
      </form>
      <UnsavedChangesDialog control={unsavedChanges} />
    </section>
  )
}
