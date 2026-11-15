// Calls to the read-only dev API. Only GET requests, and no cookies:
// the dev API does not use the session of the main app.
import type { Bucket, DevStatus, DevUser, Overview, RawBuckets, Task, TaskPage } from './types.ts'
import type { ViewState } from './url.ts'

const BASE = '/dev/api'

export class DevApiError extends Error {
  readonly status: number
  readonly detail: string | null

  constructor(status: number, detail: string | null) {
    super(detail ? `HTTP ${status}: ${detail}` : `HTTP ${status}`)
    this.name = 'DevApiError'
    this.status = status
    this.detail = detail
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(BASE + path, {
    method: 'GET',
    credentials: 'omit',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  })
  if (!response.ok) {
    let detail: string | null = null
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // The body is not JSON: keep the status code only.
    }
    throw new DevApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const fetchOverview = (signal?: AbortSignal) => getJson<Overview>('/overview', signal)
export const fetchUsers = (signal?: AbortSignal) => getJson<DevUser[]>('/users', signal)
export const fetchStatus = (signal?: AbortSignal) => getJson<DevStatus>('/status', signal)
export const fetchTask = (id: string, signal?: AbortSignal) =>
  getJson<Task>(`/tasks/${encodeURIComponent(id)}`, signal)

/** The parts of the view that select the rows of the table. */
export type TaskQuery = Omit<ViewState, 'task'>

export function fetchTasks(view: TaskQuery, signal?: AbortSignal): Promise<TaskPage> {
  const params = new URLSearchParams()
  if (view.user_id) params.set('user_id', view.user_id)
  if (view.status) params.set('status', view.status)
  if (view.priority) params.set('priority', view.priority)
  if (view.project) params.set('project', view.project)
  if (view.hashtag) params.set('hashtag', view.hashtag)
  if (view.q) params.set('q', view.q)
  if (view.include_deleted) params.set('include_deleted', 'true')
  params.set('sort', view.sort)
  params.set('order', view.order)
  params.set('limit', String(view.limit))
  params.set('offset', String((view.page - 1) * view.limit))
  return getJson<TaskPage>(`/tasks?${params.toString()}`, signal)
}

/** Turns a distribution sent as a list or as an object into buckets, largest first. */
export function normalizeBuckets(raw: RawBuckets | null | undefined): Bucket[] {
  if (!raw) return []
  const buckets: Bucket[] = Array.isArray(raw)
    ? raw.map((b) => ({ value: b.value ?? b.key ?? b.name ?? null, count: b.count }))
    : Object.entries(raw).map(([value, count]) => ({ value, count }))
  return buckets.sort((a, b) => b.count - a.count)
}

/** Message for the error banner. */
export function describeError(error: unknown): { title: string; message: string } {
  if (error instanceof DevApiError) {
    if (error.status === 404) {
      return {
        title: 'Dev UI is disabled',
        message: 'Set DEV_UI_ENABLED=true in backend/.env and restart the API.',
      }
    }
    if (error.status === 403) {
      return {
        title: 'Access refused',
        message:
          'The dev API answers only to clients on this machine with a localhost Host header. Open the page from http://localhost.' +
          (error.detail && error.detail !== 'Forbidden' ? ` (${error.detail})` : ''),
      }
    }
    return { title: `The dev API answered ${error.status}`, message: error.detail ?? 'Unexpected error.' }
  }
  if (error instanceof Error) {
    return { title: 'Cannot reach the dev API', message: error.message }
  }
  return { title: 'Cannot reach the dev API', message: String(error) }
}
