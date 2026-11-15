import type { DevStatus } from './types.ts'
import { absoluteDate } from './format.ts'

interface Props {
  status: DevStatus | null
  loading: boolean
  loadedAt: number | null
  onRefresh: () => void
}

export default function Header({ status, loading, loadedAt, onRefresh }: Props) {
  const jobs = status?.jobs ?? []
  const jobsTitle = jobs.length
    ? jobs.map((j) => `${j.id}: next run ${j.next_run_time ? absoluteDate(j.next_run_time) : 'none'}`).join('\n')
    : 'No scheduled jobs'

  return (
    <header className="dv-header">
      <div className="dv-header__title">
        <h1>Data viewer</h1>
        <span className="dv-badge" title="Shows the local database as it is now. It changes nothing.">
          local · read-only
        </span>
      </div>
      <div className="dv-header__meta">
        {status ? (
          <>
            <span title="Alembic revision of the database">
              db rev <code>{status.alembic_revision || 'unknown'}</code>
            </span>
            <span className="dv-dot-sep" aria-hidden="true">·</span>
            <span title={jobsTitle}>
              <span className={status.scheduler_running ? 'dv-led dv-led--on' : 'dv-led'} aria-hidden="true" />
              scheduler {status.scheduler_running ? 'on' : 'off'}
              {jobs.length > 0 && ` (${jobs.length} job${jobs.length === 1 ? '' : 's'})`}
            </span>
          </>
        ) : loading ? (
          <span className="dv-skeleton dv-skeleton--text" style={{ width: '14rem' }} />
        ) : (
          <span>status unavailable</span>
        )}
        {loadedAt !== null && (
          <>
            <span className="dv-dot-sep" aria-hidden="true">·</span>
            <span title={new Date(loadedAt).toLocaleString()}>
              loaded {new Date(loadedAt).toLocaleTimeString()}
            </span>
          </>
        )}
        <button
          type="button"
          className="dv-button dv-button--icon"
          onClick={onRefresh}
          disabled={loading}
          title="Reload everything from the database"
          aria-label="Refresh"
        >
          <span className={loading ? 'dv-spin' : undefined} aria-hidden="true">⟳</span>
        </button>
      </div>
    </header>
  )
}
