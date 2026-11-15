import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DevApiError,
  describeError,
  fetchOverview,
  fetchStatus,
  fetchTask,
  fetchTasks,
  fetchUsers,
  normalizeBuckets,
  type TaskQuery,
} from './api.ts'
import FilterBar from './FilterBar.tsx'
import Header from './Header.tsx'
import OverviewPanel from './OverviewPanel.tsx'
import TaskDrawer from './TaskDrawer.tsx'
import TaskTable from './TaskTable.tsx'
import type { DevStatus, DevUser, Overview, SortColumn, Task, TaskPage } from './types.ts'
import { DEFAULT_VIEW, readView, writeView, type ViewState } from './url.ts'

const SEARCH_DEBOUNCE_MS = 300

interface Meta {
  overview: Overview
  users: DevUser[]
  status: DevStatus
  loadedAt: number
}

// Each result remembers the request it answers, so "loading" is derived by
// comparing it with the current request instead of being set in an effect.
type MetaResult = { reload: number } & ({ ok: true; meta: Meta } | { ok: false; error: unknown })
type TasksResult = { query: TaskQuery; reload: number } & ({ ok: true; page: TaskPage } | { ok: false; error: unknown })
type DetailResult = { id: string; reload: number } & ({ ok: true; task: Task } | { ok: false; error: unknown })

const taskErrorLine = (error: unknown) => {
  const { title, message } = describeError(error, 'task')
  return `${title}. ${message}`
}

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError'

export default function DevApp() {
  const [view, setView] = useState<ViewState>(() => readView(window.location.search))
  const [searchText, setSearchText] = useState(view.q)
  const [reload, setReload] = useState(0)
  const [metaResult, setMetaResult] = useState<MetaResult | null>(null)
  const [tasksResult, setTasksResult] = useState<TasksResult | null>(null)
  const [detailResult, setDetailResult] = useState<DetailResult | null>(null)
  // Last successful data, kept on screen while a new request is running.
  const [meta, setMeta] = useState<Meta | null>(null)
  const [tasks, setTasks] = useState<TaskPage | null>(null)
  // Reference time for relative dates: the time of the last successful load.
  const [now, setNow] = useState(0)

  // The URL is the only place where the view is kept.
  useEffect(() => {
    writeView(view)
  }, [view])

  // Debounced text search.
  useEffect(() => {
    if (searchText === view.q) return
    const timer = window.setTimeout(() => {
      setView((v) => ({ ...v, q: searchText, page: 1 }))
    }, SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [searchText, view.q])

  // Header and overview data.
  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    Promise.all([fetchOverview(signal), fetchUsers(signal), fetchStatus(signal)]).then(
      ([overview, users, status]) => {
        const loaded: Meta = { overview, users, status, loadedAt: Date.now() }
        setMeta(loaded)
        setNow(loaded.loadedAt)
        setMetaResult({ reload, ok: true, meta: loaded })
      },
      (error: unknown) => {
        if (!isAbort(error)) setMetaResult({ reload, ok: false, error })
      },
    )
    return () => controller.abort()
  }, [reload])

  const taskQuery = useMemo<TaskQuery>(
    () => ({
      user_id: view.user_id,
      status: view.status,
      priority: view.priority,
      project: view.project,
      hashtag: view.hashtag,
      q: view.q,
      include_deleted: view.include_deleted,
      sort: view.sort,
      order: view.order,
      page: view.page,
      limit: view.limit,
    }),
    [
      view.user_id,
      view.status,
      view.priority,
      view.project,
      view.hashtag,
      view.q,
      view.include_deleted,
      view.sort,
      view.order,
      view.page,
      view.limit,
    ],
  )

  // Table rows.
  useEffect(() => {
    const controller = new AbortController()
    fetchTasks(taskQuery, controller.signal).then(
      (page) => {
        setTasks(page)
        setNow(Date.now())
        setTasksResult({ query: taskQuery, reload, ok: true, page })
      },
      (error: unknown) => {
        if (!isAbort(error)) setTasksResult({ query: taskQuery, reload, ok: false, error })
      },
    )
    return () => controller.abort()
  }, [taskQuery, reload])

  // Task open in the drawer.
  useEffect(() => {
    if (!view.task) return
    const controller = new AbortController()
    const id = view.task
    fetchTask(id, controller.signal).then(
      (task) => setDetailResult({ id, reload, ok: true, task }),
      (error: unknown) => {
        if (!isAbort(error)) setDetailResult({ id, reload, ok: false, error })
      },
    )
    return () => controller.abort()
  }, [view.task, reload])

  const metaLoading = metaResult?.reload !== reload
  const tasksLoading = !(tasksResult && tasksResult.query === taskQuery && tasksResult.reload === reload)

  // One banner for the whole page: 404 and 403 make every call fail the same way.
  const errors = [
    !metaLoading && metaResult && !metaResult.ok ? metaResult.error : null,
    !tasksLoading && tasksResult && !tasksResult.ok ? tasksResult.error : null,
  ].filter((e) => e !== null)
  const blocking = errors.find((e) => e instanceof DevApiError && (e.status === 404 || e.status === 403))
  const banner = blocking ?? errors[0]

  const userEmails = useMemo(() => new Map((meta?.users ?? []).map((u) => [u.id, u.email])), [meta])
  const overview = meta?.overview ?? null

  const update = useCallback((patch: Partial<ViewState>) => {
    setView((v) => ({ ...v, page: 1, ...patch }))
  }, [])

  const toggleFilter = useCallback(
    (key: 'status' | 'priority' | 'project' | 'hashtag', value: string) => {
      setView((v) => ({ ...v, page: 1, [key]: v[key] === value ? '' : value }))
    },
    [],
  )

  const clearFilters = useCallback(() => {
    setSearchText('')
    setView((v) => ({ ...DEFAULT_VIEW, sort: v.sort, order: v.order, limit: v.limit }))
  }, [])

  const sortBy = useCallback((column: SortColumn) => {
    setView((v) => ({
      ...v,
      page: 1,
      sort: column,
      order: v.sort === column ? (v.order === 'asc' ? 'desc' : 'asc') : column === 'updated' ? 'desc' : 'asc',
    }))
  }, [])

  const closeDrawer = useCallback(() => setView((v) => ({ ...v, task: '' })), [])

  const hasFilters = !!(view.user_id || view.status || view.priority || view.project || view.hashtag || view.q)

  const detail = detailResult && detailResult.id === view.task && detailResult.reload === reload ? detailResult : null
  const bannerText = banner ? describeError(banner) : null
  const showContent = !blocking

  return (
    <div className="dv-app">
      <Header
        status={meta?.status ?? null}
        loading={metaLoading || tasksLoading}
        loadedAt={meta?.loadedAt ?? null}
        onRefresh={() => setReload((r) => r + 1)}
      />
      <main className="dv-main">
        {bannerText && (
          <div className="dv-banner dv-banner--error" role="alert">
            {blocking instanceof DevApiError && blocking.status === 404 ? (
              <span>
                <strong>Dev UI is disabled:</strong> set <code>DEV_UI_ENABLED=true</code> in{' '}
                <code>backend/.env</code> and restart the API.
              </span>
            ) : (
              <span>
                <strong>{bannerText.title}.</strong> {bannerText.message}
              </span>
            )}
            <button type="button" className="dv-button" onClick={() => setReload((r) => r + 1)}>
              Retry
            </button>
          </div>
        )}
        {showContent && (
          <>
            <OverviewPanel
              overview={overview}
              view={view}
              now={now}
              onFilter={toggleFilter}
              onShowDeleted={() => update({ include_deleted: !view.include_deleted })}
            />
            <FilterBar
              view={view}
              users={meta?.users ?? []}
              statuses={normalizeBuckets(overview?.by_status)}
              priorities={normalizeBuckets(overview?.by_priority)}
              projects={normalizeBuckets(overview?.by_project_name)}
              hashtags={normalizeBuckets(overview?.by_hashtag).map((b) => ({
                ...b,
                value: b.value ? b.value.replace(/^#/, '') : b.value,
              }))}
              searchText={searchText}
              onSearchText={setSearchText}
              onSelect={(key, value) => update({ [key]: value })}
              onIncludeDeleted={(value) => update({ include_deleted: value })}
              onClear={clearFilters}
            />
            <TaskTable
              page={tasks}
              loading={tasksLoading}
              now={now}
              sort={view.sort}
              order={view.order}
              pageNumber={view.page}
              limit={view.limit}
              selectedId={view.task}
              userEmails={userEmails}
              hasFilters={hasFilters || view.include_deleted}
              onSort={sortBy}
              onPage={(page) => setView((v) => ({ ...v, page }))}
              onLimit={(limit) => update({ limit })}
              onOpen={(task) => setView((v) => ({ ...v, task }))}
              onClear={clearFilters}
            />
          </>
        )}
      </main>
      {showContent && view.task && (
        <TaskDrawer
          taskId={view.task}
          task={detail && detail.ok ? detail.task : null}
          error={detail && !detail.ok ? taskErrorLine(detail.error) : null}
          now={now}
          userEmails={userEmails}
          onClose={closeDrawer}
        />
      )}
    </div>
  )
}
