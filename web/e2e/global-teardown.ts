import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

export default function globalTeardown() {
  const result = spawnSync(
    resolve(process.cwd(), '../backend/.venv/bin/python'),
    ['-m', 'trialsync.demo', 'prepare-e2e'],
    { cwd: process.cwd(), stdio: 'inherit' },
  )
  if (result.status !== 0) {
    throw new Error('Could not restore the fixed Phase 8 demo after browser tests.')
  }
}
