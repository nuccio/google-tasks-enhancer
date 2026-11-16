import type { Bucket, Overview } from './types.ts'
import { normalizeBuckets } from './api.ts'
import { EMPTY, absoluteDate, relativeDate } from './format.ts'
import type { ViewState } from './url.ts'

type FilterKey = 'status' | 'priority' | 'project' | 'hashtag'

interface Props {
  overview: Overview | null
  view: ViewState
  now: number
  onFilter: (key: FilterKey, value: string) => void
  onShowDeleted: () => void
}

function countOf(buckets: Bucket[], value: string): number {
  return buckets.find((b) => b.value === value)?.count ?? 0
}

interface CardProps {
  label: string
  value: number | string
  hint?: string
  warn?: boolean
  active?: boolean
  onClick?: () => void
}

function Card({ label, value, hint, warn, active, onClick }: CardProps) {
  const className = ['dv-card', warn ? 'dv-card--warn' : '', active ? 'dv-card--active' : '', onClick ? 'dv-card--click' : '']
    .filter(Boolean)
    .join(' ')
  const body = (
    <>
      <span className="dv-card__label">{label}</span>
      <span className="dv-card__value">{value}</span>
    </>
  )
  return onClick ? (
    <button type="button" className={className} title={hint} onClick={onClick} aria-pressed={active}>
      {body}
    </button>
  ) : (
    <div className={className} title={hint}>
      {body}
    </div>
  )
}

interface BarsProps {
  title: string
  buckets: Bucket[]
  active: string
  onPick: (value: string) => void
}

function Bars({ title, buckets, active, onPick }: BarsProps) {
  const max = Math.max(1, ...buckets.map((b) => b.count))
  return (
    <section className="dv-bars" aria-label={title}>
      <h2>{title}</h2>
      {buckets.length === 0 ? (
        <p className="dv-muted">{EMPTY}</p>
      ) : (
        <ul>
          {buckets.map((b) => {
            const label = b.value ?? '(empty)'
            const clickable = b.value !== null && b.value !== ''
            const isActive = clickable && active === b.value
            return (
              <li key={label}>
                <button
                  type="button"
                  className={isActive ? 'dv-bar dv-bar--active' : 'dv-bar'}
                  disabled={!clickable}
                  aria-pressed={isActive}
                  title={clickable ? `Filter by ${label}` : 'Empty values cannot be used as a filter'}
                  onClick={() => clickable && onPick(b.value as string)}
                >
                  <span className="dv-bar__label">{label}</span>
                  <span className="dv-bar__track">
                    <span className="dv-bar__fill" style={{ width: `${(b.count / max) * 100}%` }} />
                  </span>
                  <span className="dv-bar__count">{b.count}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function OverviewSkeleton() {
  return (
    <div className="dv-overview" aria-busy="true" aria-label="Loading overview">
      <div className="dv-cards">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="dv-card dv-skeleton dv-skeleton--card" />
        ))}
      </div>
      <div className="dv-dists">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="dv-bars">
            <span className="dv-skeleton dv-skeleton--text" style={{ width: '40%' }} />
            <span className="dv-skeleton dv-skeleton--text" />
            <span className="dv-skeleton dv-skeleton--text" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function OverviewPanel({ overview, view, now, onFilter, onShowDeleted }: Props) {
  if (!overview) return <OverviewSkeleton />

  const byStatus = normalizeBuckets(overview.by_status)
  const byPriority = normalizeBuckets(overview.by_priority)
  const byProject = normalizeBuckets(overview.by_project_name)
  const byHashtag = normalizeBuckets(overview.by_hashtag).map((b) => ({
    ...b,
    value: b.value ? b.value.replace(/^#/, '') : b.value,
  }))

  return (
    <div className="dv-overview">
      <div className="dv-cards">
        <Card label="Users" value={overview.users} />
        <Card label="Tasks" value={overview.tasks} />
        <Card
          label="Open"
          value={countOf(byStatus, 'needsAction')}
          hint="Status needsAction: click to filter"
          active={view.status === 'needsAction'}
          onClick={() => onFilter('status', 'needsAction')}
        />
        <Card
          label="Done"
          value={countOf(byStatus, 'completed')}
          hint="Status completed: click to filter"
          active={view.status === 'completed'}
          onClick={() => onFilter('status', 'completed')}
        />
        <Card
          label="Deleted · hidden"
          value={`${overview.deleted} · ${overview.hidden}`}
          hint="Deleted tasks are left out of the table unless asked for: click to show them. Hidden tasks (completed in a Google app) are always shown"
          active={view.include_deleted}
          onClick={onShowDeleted}
        />
        <Card
          label="No tasklist_id"
          value={overview.without_tasklist_id}
          warn={overview.without_tasklist_id > 0}
          hint="These tasks cannot be updated on Google"
        />
        <Card label="No due date" value={overview.without_due_date} />
        <Card
          label="Last updated"
          value={overview.last_updated ? relativeDate(overview.last_updated, now) : EMPTY}
          hint={overview.last_updated ? absoluteDate(overview.last_updated) : undefined}
        />
      </div>
      <div className="dv-dists">
        <Bars title="By status" buckets={byStatus} active={view.status} onPick={(v) => onFilter('status', v)} />
        <Bars title="By priority" buckets={byPriority} active={view.priority} onPick={(v) => onFilter('priority', v)} />
        <Bars title="By project" buckets={byProject} active={view.project} onPick={(v) => onFilter('project', v)} />
        <section className="dv-bars" aria-label="Hashtags">
          <h2>Hashtags (top 20)</h2>
          {byHashtag.length === 0 ? (
            <p className="dv-muted">{EMPTY}</p>
          ) : (
            <div className="dv-chips">
              {byHashtag.map((b) =>
                b.value ? (
                  <button
                    key={b.value}
                    type="button"
                    className={view.hashtag === b.value ? 'dv-chip dv-chip--active' : 'dv-chip'}
                    aria-pressed={view.hashtag === b.value}
                    title={`Filter by #${b.value}`}
                    onClick={() => onFilter('hashtag', b.value as string)}
                  >
                    #{b.value} <span className="dv-chip__count">{b.count}</span>
                  </button>
                ) : null,
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
