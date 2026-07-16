import { expect, test, type Page } from '@playwright/test'

const demoEmail = 'demo@trialsync.example'
const demoPassword = 'SyntheticDemo123!'
const seededBatchId = 'dfcd9af2-9047-594e-ab85-a5dfd65f38db'

async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(demoEmail)
  await page.getByLabel('Password').fill(demoPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Evidence before a decision.' })).toBeVisible()
}

async function selectMatching(page: Page, label: string, optionText: string) {
  const select = page.getByRole('combobox', { name: label, exact: true })
  const value = await select.locator('option').filter({ hasText: optionText }).getAttribute('value')
  if (!value) throw new Error(`No ${label} option matched ${optionText}.`)
  await select.selectOption(value)
}

test.describe.configure({ mode: 'serial' })

test('registration through manual screening history', async ({ page }) => {
  const email = 'phase8-browser@trialsync.example'
  await page.goto('/register')
  await page.getByRole('textbox', { name: 'Display name' }).fill('Phase 8 Browser Reviewer')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password').fill('SyntheticBrowser123!')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Evidence before a decision.' })).toBeVisible()

  await page.goto('/patients/new')
  await page.getByRole('textbox', { name: 'Display name' }).fill('Synthetic Browser Patient')
  await page.getByLabel('Date of birth').fill('1985-01-10')
  await page.getByRole('button', { name: 'Create patient' }).click()
  await expect(page.getByRole('heading', { name: 'Synthetic Browser Patient' })).toBeVisible()

  await page.goto('/trials/new')
  await page.getByRole('textbox', { name: 'Trial title' }).fill('Synthetic Browser Age Trial')
  await page.getByRole('textbox', { name: 'Condition' }).fill('Synthetic browser condition')
  await page.getByRole('button', { name: 'Create trial' }).click()
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByText('Version 1')).toBeVisible()
  await page.getByRole('textbox', { name: 'Criterion wording' }).fill('Age 18 to 75 years')
  await page.getByRole('button', { name: 'Add criterion' }).click()
  await expect(page.getByText('Deterministic rule reviewed')).toBeVisible()
  await page.getByRole('button', { name: 'Approve version' }).click()
  await expect(page.getByText('approved', { exact: true })).toBeVisible()

  await page.goto('/screenings/new')
  await selectMatching(page, 'Patient', 'Synthetic Browser Patient')
  await selectMatching(page, 'Approved trial version', 'Synthetic Browser Age Trial')
  await page.getByRole('button', { name: 'Run screening' }).click()
  await expect(page.getByRole('heading', { name: 'potentially eligible' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Age 18 to 75 years' })).toBeVisible()
  await page.getByRole('link', { name: '← Screening history' }).click()
  await expect(page).toHaveURL(/\/screenings$/)
  await expect(
    page.locator('.history-compact-row').filter({ hasText: 'Synthetic Browser Patient' }),
  ).toBeVisible()
})

test('seeded mixed batch renders six linked evidence cells', async ({ page }) => {
  await signIn(page)
  await page.goto('/batches/new')
  for (const name of [
    'Synthetic Ada Mercer',
    'Synthetic Ben Carter',
    'Synthetic Dev Malik',
  ]) {
    await page.getByRole('checkbox', { name: new RegExp(name) }).check()
  }
  await page.getByRole('checkbox', { name: /Synthetic metabolic eligibility study/ }).check()
  await page.getByRole('checkbox', { name: /Synthetic renal safety study/ }).check()
  await expect(page.getByText('6 screening pairs')).toBeVisible()
  await page.getByRole('button', { name: 'Run batch screening' }).click()
  await expect(page.getByRole('table')).toBeVisible()
  await expect(page.locator('.matrix-cell')).toHaveCount(6)
  await page.locator('.matrix-cell').first().click()
  await expect(page.getByRole('heading', { name: 'Criteria' })).toBeVisible()
})

test('trial text import is corrected, approved, screened, and explained', async ({ page }) => {
  await signIn(page)
  await page.goto('/imports/new?kind=trial')
  await page.getByRole('textbox', { name: 'Source text' }).fill(
    'Title: Synthetic Imported Age Trial\n' +
    'Condition: Synthetic imported condition\n' +
    'Phase: Phase 2\n' +
    'Inclusion Criteria:\n- Age 18 to 75 years',
  )
  await page.getByRole('button', { name: 'Analyze for review' }).click()
  const title = page.getByRole('textbox', { name: 'Trial title' })
  await title.fill('Synthetic Corrected Import Trial')
  await page.getByRole('button', { name: 'Approve and create trial' }).click()
  await expect(page.getByRole('heading', { name: 'Synthetic Corrected Import Trial' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve version' }).click()

  await page.goto('/screenings/new')
  await selectMatching(page, 'Patient', 'Synthetic Ada Mercer')
  await selectMatching(page, 'Approved trial version', 'Synthetic Corrected Import Trial')
  await page.getByRole('button', { name: 'Run screening' }).click()
  await expect(page.getByRole('heading', { name: 'potentially eligible' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Age 18 to 75 years' })).toBeVisible()
})

test('generated text PDF remains reviewable before patient approval', async ({ page }) => {
  await signIn(page)
  await page.goto('/imports/new?kind=patient')
  await page.getByRole('radio', { name: 'Upload PDF' }).check()
  await page.getByLabel('PDF document').setInputFiles('/tmp/trialsync-phase8.pdf')
  await page.getByRole('button', { name: 'Analyze for review' }).click()
  await expect(page.getByRole('heading', { name: 'Review extracted patient candidates' })).toBeVisible()
  await expect(page.getByText('Synthetic PDF Rowan', { exact: false }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Approve and create patient' }).click()
  await expect(page.getByRole('heading', { name: 'Synthetic PDF Rowan' })).toBeVisible()
  await expect(page.getByText('Imported document p.1').first()).toBeVisible()
})

test('needs-review conversation supports keyboard, retry, citations, refusal, and clear', async ({ page }) => {
  await signIn(page)
  const seededScreeningId = await page.evaluate(async (batchId) => {
    const token = window.sessionStorage.getItem('trialsync_access_token')
    const response = await fetch('http://127.0.0.1:8002/api/v1/screenings', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(`Screening history request failed with ${response.status}.`)
    const screenings = await response.json() as Array<{
      id: string
      batch_id: string | null
      patient_snapshot: { display_name: string }
      trial_version: { title: string }
    }>
    return screenings.find((screening) => (
      screening.batch_id === batchId
      && screening.patient_snapshot.display_name === 'Synthetic Dev Malik'
      && screening.trial_version.title === 'Synthetic metabolic eligibility study'
    ))?.id
  }, seededBatchId)
  expect(seededScreeningId).toBeTruthy()
  await page.goto(`/screenings/${seededScreeningId}`)
  await expect(page.getByRole('heading', { name: 'needs review', exact: true })).toBeVisible()
  await expect(page.getByText('Result explanation').first()).toBeVisible()
  await expect(page.getByRole('link', { name: /Criterion evidence · Age 18 to 75 years/ }).first()).toBeVisible()
  await page.reload()
  await expect(page.getByText('A date of birth is required to calculate age')).toBeVisible()

  const suggestions = page.getByLabel('Suggested questions').getByRole('button')
  await expect(suggestions).toHaveCount(3)
  const suggestionWidths = await suggestions.evaluateAll((buttons) => (
    buttons.map((button) => button.getBoundingClientRect().width)
  ))
  expect(Math.max(...suggestionWidths) - Math.min(...suggestionWidths)).toBeLessThan(2)

  let failedOnce = false
  await page.route('**/conversation/messages', async (route) => {
    if (route.request().method() !== 'POST' || failedOnce) return route.fallback()
    failedOnce = true
    await route.fulfill({
      status: 504,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'ASSISTANT_TIMEOUT', message: 'Synthetic timeout' } }),
    })
  })
  const composer = page.getByRole('textbox', { name: 'Question about this stored result' })
  await composer.fill('What information')
  await composer.press('Shift+Enter')
  await composer.pressSequentially('is missing?')
  await expect(composer).toHaveValue('What information\nis missing?')
  await composer.press('Enter')
  await expect(page.getByRole('alert')).toContainText('timed out')
  await expect(composer).toBeFocused()
  await page.getByRole('button', { name: 'Retry question' }).click()
  await expect(page.getByText('A new result explanation is ready.')).toBeAttached()
  await expect.poll(() => page.locator('.chat-transcript').evaluate((transcript) => (
    transcript.scrollTop + transcript.clientHeight >= transcript.scrollHeight - 1
  ))).toBe(true)
  await expect(composer).toBeFocused()
  await page.unroute('**/conversation/messages')

  const citation = page.getByRole('link', { name: /Criterion evidence · Age 18 to 75 years/ }).last()
  await citation.click()
  const criterion = page.locator('article:target')
  await expect(criterion).toBeFocused()
  const returnLink = criterion.getByRole('link', { name: 'Back to the result assistant' })
  await expect(returnLink).toBeVisible()
  await returnLink.click()
  await expect(page.locator('#screening-chat-panel')).toBeFocused()

  await composer.fill('Should this participant enroll?')
  await composer.press('Enter')
  await expect(page.getByText('Request declined').last()).toBeVisible()
  await page.getByRole('button', { name: 'Clear conversation' }).click()
  const dialog = page.getByRole('dialog', { name: 'Clear this conversation?' })
  await dialog.getByRole('button', { name: 'Clear conversation' }).click()
  await expect(page.getByText('What would you like to understand?')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Age 18 to 75 years at screening' })).toBeVisible()
})

test('loading, empty, error, evaluation, focus, and unknown states remain responsive', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await signIn(page)

  let releaseHistory: (() => void) | undefined
  await page.route('**/api/v1/screenings', async (route) => {
    await new Promise<void>((resolve) => { releaseHistory = resolve })
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })
  await page.reload()
  await expect(page.getByText('Loading workspace summary…')).toBeVisible()
  await page.screenshot({ path: 'test-results/dashboard-loading.png', fullPage: true })
  releaseHistory?.()
  await expect(page.getByText('No saved screenings')).toBeVisible()
  await page.screenshot({ path: 'test-results/dashboard-empty.png', fullPage: true })

  await page.unroute('**/api/v1/screenings')
  await page.route('**/api/v1/screenings', (route) => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'VISUAL_REVIEW', message: 'Synthetic review error' } }),
  }))
  await page.reload()
  await expect(page.getByRole('alert')).toHaveText('Dashboard data could not be loaded.')
  await page.screenshot({ path: 'test-results/dashboard-error.png', fullPage: true })
  await page.unroute('**/api/v1/screenings')

  await page.goto('/help')
  const helpLink = page.getByRole('link', { name: 'Help' })
  await helpLink.focus()
  await expect(helpLink).toBeFocused()
  await page.screenshot({ path: 'test-results/help-desktop.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.emulateMedia({ reducedMotion: 'reduce' })
  const routeAnimation = await page.locator('.route-entry').evaluate((element) => (
    window.getComputedStyle(element).animationDuration
  ))
  const routeAnimationMs = routeAnimation.endsWith('ms')
    ? Number.parseFloat(routeAnimation)
    : Number.parseFloat(routeAnimation) * 1_000
  expect(routeAnimationMs).toBeLessThanOrEqual(0.01)
  await page.setViewportSize({ width: 720, height: 1000 })
  await page.screenshot({ path: 'test-results/help-narrow.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  const seededScreeningId = await page.evaluate(async (batchId) => {
    const token = window.sessionStorage.getItem('trialsync_access_token')
    const response = await fetch('http://127.0.0.1:8002/api/v1/screenings', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const screenings = await response.json() as Array<{
      id: string
      batch_id: string | null
      patient_snapshot: { display_name: string }
    }>
    return screenings.find((screening) => (
      screening.batch_id === batchId
      && screening.patient_snapshot.display_name === 'Synthetic Dev Malik'
    ))?.id
  }, seededBatchId)
  expect(seededScreeningId).toBeTruthy()
  await page.goto(`/screenings/${seededScreeningId}`)
  await expect(page.getByRole('heading', { name: 'needs review', exact: true })).toBeVisible()
  await expect(page.getByText('Required information is not recorded.').first()).toBeVisible()
  await page.screenshot({ path: 'test-results/screening-unknown-narrow.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
