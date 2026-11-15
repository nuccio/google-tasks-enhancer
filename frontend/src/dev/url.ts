// The view (filters, sort, page) lives only in the URL query string.
// Nothing is stored in the browser: a reload or a copied link shows the same view.
import { SORT_COLUMNS, type SortColumn, type SortOrder } from './types.ts'

export const PAGE_SIZES = [25, 50, 100, 200] as const
const DEFAULT_LIMIT = 50

export interface ViewState {
  user_id: string
  status: string
  priority: string
  project: string
  hashtag: string
  q: string
  include_deleted: boolean
  sort: SortColumn
  order: SortOrder
  page: number
  limit: number
  /** Id of the task open in the drawer, if any. */
  task: string
}

export const DEFAULT_VIEW: ViewState = {
  user_id: '',
  status: '',
  priority: '',
  project: '',
  hashtag: '',
  q: '',
  include_deleted: false,
  sort: 'updated',
  order: 'desc',
  page: 1,
  limit: DEFAULT_LIMIT,
  task: '',
}

function positiveInt(value: string | null, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback
  const n = Number(value)
  return n >= 1 ? n : fallback
}

export function readView(search: string): ViewState {
  const p = new URLSearchParams(search)
  const sort = p.get('sort')
  const order = p.get('order')
  const limit = positiveInt(p.get('limit'), DEFAULT_LIMIT)
  return {
    user_id: p.get('user_id') ?? '',
    status: p.get('status') ?? '',
    priority: p.get('priority') ?? '',
    project: p.get('project') ?? '',
    hashtag: (p.get('hashtag') ?? '').replace(/^#/, ''),
    q: p.get('q') ?? '',
    include_deleted: p.get('include_deleted') === 'true',
    sort: SORT_COLUMNS.includes(sort as SortColumn) ? (sort as SortColumn) : DEFAULT_VIEW.sort,
    order: order === 'asc' || order === 'desc' ? order : DEFAULT_VIEW.order,
    page: positiveInt(p.get('page'), 1),
    limit: Math.min(limit, 500),
    task: p.get('task') ?? '',
  }
}

/** Query string for a view; values equal to the default are left out. */
export function viewToSearch(view: ViewState): string {
  const p = new URLSearchParams()
  if (view.user_id) p.set('user_id', view.user_id)
  if (view.status) p.set('status', view.status)
  if (view.priority) p.set('priority', view.priority)
  if (view.project) p.set('project', view.project)
  if (view.hashtag) p.set('hashtag', view.hashtag)
  if (view.q) p.set('q', view.q)
  if (view.include_deleted) p.set('include_deleted', 'true')
  if (view.sort !== DEFAULT_VIEW.sort) p.set('sort', view.sort)
  if (view.order !== DEFAULT_VIEW.order) p.set('order', view.order)
  if (view.page !== 1) p.set('page', String(view.page))
  if (view.limit !== DEFAULT_LIMIT) p.set('limit', String(view.limit))
  if (view.task) p.set('task', view.task)
  const s = p.toString()
  return s ? `?${s}` : ''
}

export function writeView(view: ViewState): void {
  const search = viewToSearch(view)
  if (search === window.location.search) return
  const url = window.location.pathname + search + window.location.hash
  window.history.replaceState(null, '', url)
}
