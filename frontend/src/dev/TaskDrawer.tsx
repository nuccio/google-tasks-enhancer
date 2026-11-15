import { useEffect, useState } from 'react'
import type { Task } from './types.ts'
import { EMPTY, absoluteDate, formatMinutes, isEmpty, priorityClass, relativeDate, statusIcon } from './format.ts'

interface Props {
  taskId: string
  task: Task | null
  error: string | null
  now: number
  userEmails: Map<number, string>
  onClose: () => void
}

const GOOGLE_FIELDS = [
  'id',
  'kind',
  'title',
  'notes',
  'status',
  'due_date',
  'completed',
  'updated',
  'parent',
  'position',
  'deleted',
  'hidden',
  'webViewLink',
  'selfLink',
  'etag',
  'assignmentInfo',
  'links',
] as const
const CUSTOM_FIELDS = ['priority', 'project_name', 'hashtags', 'estimated_time_minutes'] as const
const INTERNAL_FIELDS = ['owner_id', 'tasklist_id'] as const
const DATE_FIELDS = new Set(['due_date', 'completed', 'updated'])
const KNOWN_FIELDS = new Set<string>([...GOOGLE_FIELDS, ...CUSTOM_FIELDS, ...INTERNAL_FIELDS])

function FieldValue({
  name,
  value,
  now,
  userEmails,
}: {
  name: string
  value: unknown
  now: number
  userEmails: Map<number, string>
}) {
  if (isEmpty(value)) return <span className="dv-muted">{EMPTY}</span>
  if (DATE_FIELDS.has(name) && typeof value === 'string') {
    return (
      <span>
        <time dateTime={value}>{absoluteDate(value)}</time>{' '}
        <span className="dv-muted">({relativeDate(value, now)})</span>
      </span>
    )
  }
  if (name === 'status' && typeof value === 'string') {
    const s = statusIcon(value)
    return (
      <span>
        <span className={`dv-status dv-status--${s.label}`} aria-hidden="true">
          {s.icon}
        </span>{' '}
        {value}
      </span>
    )
  }
  if (name === 'priority' && typeof value === 'string') {
    return <span className={priorityClass(value)}>{value}</span>
  }
  if (name === 'hashtags' && Array.isArray(value)) {
    return (
      <span className="dv-chips dv-chips--inline">
        {value.map((h) => (
          <span key={String(h)} className="dv-chip dv-chip--static">
            #{String(h)}
          </span>
        ))}
      </span>
    )
  }
  if (name === 'estimated_time_minutes' && typeof value === 'number') {
    return <span>{formatMinutes(value)}</span>
  }
  if (name === 'owner_id' && typeof value === 'number') {
    const email = userEmails.get(value)
    return (
      <span>
        {value}
        {email && <span className="dv-muted"> · {email}</span>}
      </span>
    )
  }
  if ((name === 'webViewLink' || name === 'selfLink') && typeof value === 'string' && value.startsWith('https://')) {
    return (
      <a href={value} target="_blank" rel="noopener noreferrer" className="dv-break">
        {value}
      </a>
    )
  }
  if (typeof value === 'boolean') return <span>{value ? 'yes' : 'no'}</span>
  if (typeof value === 'object') {
    return <pre className="dv-json dv-json--inline">{JSON.stringify(value, null, 2)}</pre>
  }
  if (name === 'notes') return <span className="dv-prewrap">{String(value)}</span>
  return <span className="dv-break">{String(value)}</span>
}

function FieldGroup({
  title,
  names,
  task,
  now,
  userEmails,
}: {
  title: string
  names: readonly string[]
  task: Task
  now: number
  userEmails: Map<number, string>
}) {
  if (names.length === 0) return null
  const record = task as unknown as Record<string, unknown>
  return (
    <section className="dv-group">
      <h3>{title}</h3>
      <dl>
        {names.map((name) => (
          <div key={name} className="dv-group__row">
            <dt>
              <code>{name}</code>
            </dt>
            <dd>
              <FieldValue name={name} value={record[name]} now={now} userEmails={userEmails} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (state === 'idle') return
    const timer = window.setTimeout(() => setState('idle'), 1500)
    return () => window.clearTimeout(timer)
  }, [state])

  return (
    <button
      type="button"
      className="dv-button"
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => setState('copied'),
          () => setState('failed'),
        )
      }}
    >
      {state === 'copied' ? 'Copied' : state === 'failed' ? 'Copy failed' : 'Copy JSON'}
    </button>
  )
}

export default function TaskDrawer({ taskId, task, error, now, userEmails, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const otherFields = task ? Object.keys(task).filter((k) => !KNOWN_FIELDS.has(k)).sort() : []
  const json = task ? JSON.stringify(task, null, 2) : ''

  return (
    <>
      <div className="dv-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="dv-drawer" role="dialog" aria-modal="true" aria-label="Task detail">
        <header className="dv-drawer__header">
          <div>
            <p className="dv-muted dv-break">
              <code>{taskId}</code>
            </p>
            <h2>{task ? (isEmpty(task.title) ? '(no title)' : task.title) : error ? 'Cannot load the task' : 'Loading…'}</h2>
          </div>
          <button type="button" className="dv-button dv-button--icon" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="dv-drawer__body">
          {error && <div className="dv-banner dv-banner--error">{error}</div>}
          {!task && !error && (
            <div aria-busy="true">
              {Array.from({ length: 10 }, (_, i) => (
                <span key={i} className="dv-skeleton dv-skeleton--text" />
              ))}
            </div>
          )}
          {task && (
            <>
              <FieldGroup title="Google fields" names={GOOGLE_FIELDS} task={task} now={now} userEmails={userEmails} />
              <FieldGroup title="Custom fields" names={CUSTOM_FIELDS} task={task} now={now} userEmails={userEmails} />
              <FieldGroup title="Internal fields" names={INTERNAL_FIELDS} task={task} now={now} userEmails={userEmails} />
              <FieldGroup title="Other fields" names={otherFields} task={task} now={now} userEmails={userEmails} />
              <section className="dv-group">
                <div className="dv-group__head">
                  <h3>Raw JSON</h3>
                  <CopyButton text={json} />
                </div>
                <pre className="dv-json">{json}</pre>
              </section>
            </>
          )}
        </div>
      </aside>
    </>
  )
}
