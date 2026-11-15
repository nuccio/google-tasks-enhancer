import type { SortColumn, SortOrder, TaskPage, TaskSummary } from './types.ts'
import { EMPTY, absoluteDate, isEmpty, priorityClass, relativeDate, statusIcon } from './format.ts'
import { PAGE_SIZES } from './url.ts'

interface Props {
  page: TaskPage | null
  loading: boolean
  now: number
  sort: SortColumn
  order: SortOrder
  pageNumber: number
  limit: number
  selectedId: string
  userEmails: Map<number, string>
  hasFilters: boolean
  onSort: (column: SortColumn) => void
  onPage: (page: number) => void
  onLimit: (limit: number) => void
  onOpen: (id: string) => void
  onClear: () => void
}

interface ColumnDef {
  label: string
  sort?: SortColumn
  className?: string
}

const COLUMNS: ColumnDef[] = [
  { label: 'Status', sort: 'status', className: 'dv-col-status' },
  { label: 'Title', sort: 'title', className: 'dv-col-title' },
  { label: 'Priority', sort: 'priority' },
  { label: 'Project', sort: 'project_name' },
  { label: 'Hashtags' },
  { label: 'Due', sort: 'due_date' },
  { label: 'Updated', sort: 'updated' },
  { label: 'User' },
]

function DateCell({ value, now }: { value: string | null | undefined; now: number }) {
  if (isEmpty(value)) return <span className="dv-muted">{EMPTY}</span>
  return (
    <time dateTime={value ?? undefined} title={absoluteDate(value)}>
      {relativeDate(value, now)}
    </time>
  )
}

function Row({
  task,
  now,
  selected,
  userEmails,
  onOpen,
}: {
  task: TaskSummary
  now: number
  selected: boolean
  userEmails: Map<number, string>
  onOpen: (id: string) => void
}) {
  const s = statusIcon(task.status)
  const classes = ['dv-row']
  if (task.deleted) classes.push('dv-row--deleted')
  if (task.hidden) classes.push('dv-row--hidden')
  if (selected) classes.push('dv-row--selected')
  const owner = task.owner_id === null || task.owner_id === undefined ? null : task.owner_id
  return (
    <tr
      className={classes.join(' ')}
      tabIndex={0}
      aria-selected={selected}
      onClick={() => onOpen(task.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen(task.id)
        }
      }}
    >
      <td className="dv-col-status">
        <span className={`dv-status dv-status--${s.label}`} title={s.label} aria-label={s.label}>
          {s.icon}
        </span>
      </td>
      <td className="dv-col-title">
        <span className="dv-title">{isEmpty(task.title) ? <span className="dv-muted">(no title)</span> : task.title}</span>
        {task.deleted && <span className="dv-flag dv-flag--deleted">deleted</span>}
        {task.hidden && <span className="dv-flag">hidden</span>}
      </td>
      <td>
        {isEmpty(task.priority) ? (
          <span className="dv-muted">{EMPTY}</span>
        ) : (
          <span className={priorityClass(task.priority)}>{task.priority}</span>
        )}
      </td>
      <td>{isEmpty(task.project_name) ? <span className="dv-muted">{EMPTY}</span> : task.project_name}</td>
      <td>
        {isEmpty(task.hashtags) ? (
          <span className="dv-muted">{EMPTY}</span>
        ) : (
          <span className="dv-chips dv-chips--inline">
            {(task.hashtags ?? []).map((h) => (
              <span key={h} className="dv-chip dv-chip--static">
                #{h}
              </span>
            ))}
          </span>
        )}
      </td>
      <td>
        <DateCell value={task.due_date} now={now} />
      </td>
      <td>
        <DateCell value={task.updated} now={now} />
      </td>
      <td className="dv-col-user">
        {owner === null ? <span className="dv-muted">{EMPTY}</span> : (userEmails.get(owner) ?? `#${owner}`)}
      </td>
    </tr>
  )
}

/** Page numbers to show: first, last, and two around the current one. */
function pageList(current: number, last: number): Array<number | 'gap'> {
  const pages = new Set([1, last, current - 2, current - 1, current, current + 1, current + 2])
  const sorted = [...pages].filter((p) => p >= 1 && p <= last).sort((a, b) => a - b)
  const result: Array<number | 'gap'> = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) result.push('gap')
    result.push(p)
  })
  return result
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <tr key={i} className="dv-row dv-row--skeleton" aria-hidden="true">
          {COLUMNS.map((c) => (
            <td key={c.label}>
              <span className="dv-skeleton dv-skeleton--text" />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

export default function TaskTable(props: Props) {
  const { page, loading, now, sort, order, pageNumber, limit } = props
  const total = page?.total ?? 0
  const lastPage = Math.max(1, Math.ceil(total / limit))
  const first = total === 0 ? 0 : (pageNumber - 1) * limit + 1
  const last = Math.min(total, pageNumber * limit)
  const items = page?.items ?? []

  return (
    <section className="dv-table-wrap" aria-busy={loading}>
      <div className="dv-table-scroll">
        <table className={loading && page ? 'dv-table dv-table--stale' : 'dv-table'}>
          <thead>
            <tr>
              {COLUMNS.map((c) => {
                const active = c.sort === sort
                return (
                  <th
                    key={c.label}
                    className={c.className}
                    scope="col"
                    aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : undefined}
                  >
                    {c.sort ? (
                      <button
                        type="button"
                        className={active ? 'dv-sort dv-sort--active' : 'dv-sort'}
                        onClick={() => props.onSort(c.sort as SortColumn)}
                        title={`Sort by ${c.sort}`}
                      >
                        {c.label}
                        <span className="dv-sort__arrow" aria-hidden="true">
                          {active ? (order === 'asc' ? '▲' : '▼') : '↕'}
                        </span>
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {!page ? (
              <SkeletonRows count={8} />
            ) : (
              items.map((t) => (
                <Row
                  key={t.id}
                  task={t}
                  now={now}
                  selected={t.id === props.selectedId}
                  userEmails={props.userEmails}
                  onOpen={props.onOpen}
                />
              ))
            )}
          </tbody>
        </table>
        {page && items.length === 0 && (
          <div className="dv-empty">
            {total > 0 ? (
              <>
                <p>Page {pageNumber} is past the last page ({lastPage}).</p>
                <button type="button" className="dv-button" onClick={() => props.onPage(1)}>
                  Go to the first page
                </button>
              </>
            ) : props.hasFilters ? (
              <>
                <p>No tasks match these filters.</p>
                <button type="button" className="dv-button" onClick={props.onClear}>
                  Clear the filters
                </button>
              </>
            ) : (
              <p>The database has no tasks yet. Log in to the app and run a sync to fill it.</p>
            )}
          </div>
        )}
      </div>
      {page && total > 0 && (
        <nav className="dv-pager" aria-label="Pages">
          <span className="dv-muted">
            {first}–{last} of {total}
          </span>
          <span className="dv-pager__pages">
            <button
              type="button"
              className="dv-button dv-button--icon"
              disabled={pageNumber <= 1}
              onClick={() => props.onPage(pageNumber - 1)}
              aria-label="Previous page"
            >
              ‹
            </button>
            {pageList(Math.min(pageNumber, lastPage), lastPage).map((p, i) =>
              p === 'gap' ? (
                <span key={`gap-${i}`} className="dv-muted">
                  …
                </span>
              ) : (
                <button
                  key={p}
                  type="button"
                  className={p === pageNumber ? 'dv-button dv-button--page dv-button--current' : 'dv-button dv-button--page'}
                  aria-current={p === pageNumber ? 'page' : undefined}
                  onClick={() => props.onPage(p)}
                >
                  {p}
                </button>
              ),
            )}
            <button
              type="button"
              className="dv-button dv-button--icon"
              disabled={pageNumber >= lastPage}
              onClick={() => props.onPage(pageNumber + 1)}
              aria-label="Next page"
            >
              ›
            </button>
          </span>
          <label className="dv-field dv-field--compact">
            <span>per page</span>
            <select value={limit} onChange={(e) => props.onLimit(Number(e.target.value))}>
              {[...new Set([...PAGE_SIZES, limit])]
                .sort((a, b) => a - b)
                .map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
            </select>
          </label>
        </nav>
      )}
    </section>
  )
}
