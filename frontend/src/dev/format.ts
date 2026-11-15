// Formatting helpers. Pure functions: the current time is passed in by the caller.

export const EMPTY = '—'

export function isEmpty(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  )
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function absoluteDate(value: string | null | undefined): string {
  const d = parseDate(value)
  return d ? d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : (value ?? '')
}

const UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

// English, like the rest of the page; absolute dates use the browser locale.
const relativeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto', style: 'short' })

/** "in 2 days", "3 hr. ago"; an empty string when the date is missing or invalid. */
export function relativeDate(value: string | null | undefined, now: number): string {
  const d = parseDate(value)
  if (!d) return value ?? ''
  const seconds = Math.round((d.getTime() - now) / 1000)
  const abs = Math.abs(seconds)
  for (const [unit, size] of UNITS) {
    if (abs >= size) return relativeFormat.format(Math.round(seconds / size), unit)
  }
  return relativeFormat.format(0, 'minute')
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return EMPTY
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h} h ${m} min` : `${h} h`
}

export function priorityClass(priority: string | null | undefined): string {
  switch ((priority ?? '').toLowerCase()) {
    case 'high':
      return 'dv-prio dv-prio--high'
    case 'medium':
      return 'dv-prio dv-prio--medium'
    case 'low':
      return 'dv-prio dv-prio--low'
    default:
      return 'dv-prio'
  }
}

export function statusIcon(status: string | null | undefined): { icon: string; label: string } {
  if (status === 'completed') return { icon: '✓', label: 'completed' }
  if (status === 'needsAction') return { icon: '○', label: 'needsAction' }
  return { icon: '?', label: status ?? 'no status' }
}
