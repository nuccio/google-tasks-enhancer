// Response types of the read-only dev API under /dev/api (#43, #45).
// Task field names match the columns of the Task model in backend/models.py.

/** One bucket of a distribution: a column value and how many tasks have it. */
export interface Bucket {
  value: string | null
  count: number
}

/**
 * A distribution as the API may send it: a list of buckets, or an object
 * that maps each value to its count. `normalizeBuckets` turns both into `Bucket[]`.
 */
export type RawBuckets =
  | Array<{ value?: string | null; key?: string | null; name?: string | null; count: number }>
  | Record<string, number>

export interface Overview {
  users: number
  tasks: number
  by_status: RawBuckets
  by_priority: RawBuckets
  by_project: RawBuckets
  /** Top 20 hashtags. */
  by_hashtag: RawBuckets
  deleted: number
  hidden: number
  without_tasklist_id: number
  without_due_date: number
  /** Most recent `updated` value among the tasks, RFC 3339. */
  last_updated: string | null
}

export interface DevUser {
  id: number
  email: string
  task_count: number
  has_google_tokens: boolean
}

/** Every column of a task, as returned by /dev/api/tasks/{id}. */
export interface Task {
  // Google Tasks fields
  id: string
  kind: string | null
  etag: string | null
  title: string | null
  updated: string | null
  selfLink: string | null
  parent: string | null
  position: string | null
  notes: string | null
  status: string | null
  due_date: string | null
  completed: string | null
  deleted: boolean | null
  hidden: boolean | null
  webViewLink: string | null
  assignmentInfo: unknown
  links: unknown
  // Custom fields
  priority: string | null
  project_name: string | null
  hashtags: string[] | null
  estimated_time_minutes: number | null
  // Internal fields
  tasklist_id: string | null
  owner_id: number | null
}

/**
 * A row of /dev/api/tasks. The list may carry fewer columns than the detail,
 * so everything except `id` is optional here.
 */
export type TaskSummary = Pick<Task, 'id'> & Partial<Omit<Task, 'id'>>

export interface TaskPage {
  total: number
  items: TaskSummary[]
}

export interface SchedulerJob {
  id: string
  next_run_time: string | null
}

export interface DevStatus {
  /** Current Alembic revision, or `unknown`. */
  alembic_revision: string
  scheduler_running: boolean
  jobs: SchedulerJob[]
}

export const SORT_COLUMNS = ['title', 'updated', 'due_date', 'priority', 'project_name', 'status'] as const
export type SortColumn = (typeof SORT_COLUMNS)[number]
export type SortOrder = 'asc' | 'desc'
