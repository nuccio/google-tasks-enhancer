import type { Bucket, DevUser } from './types.ts'
import type { ViewState } from './url.ts'

type SelectKey = 'user_id' | 'status' | 'priority' | 'project' | 'hashtag'

interface Props {
  view: ViewState
  users: DevUser[]
  statuses: Bucket[]
  priorities: Bucket[]
  projects: Bucket[]
  hashtags: Bucket[]
  searchText: string
  onSearchText: (text: string) => void
  onSelect: (key: SelectKey, value: string) => void
  onIncludeDeleted: (value: boolean) => void
  onClear: () => void
}

interface Option {
  value: string
  label: string
}

/** Options from the overview, plus the current value when the overview does not list it. */
function optionsFrom(buckets: Bucket[], current: string, prefix = ''): Option[] {
  const options: Option[] = buckets
    .filter((b): b is { value: string; count: number } => !!b.value)
    .map((b) => ({ value: b.value, label: `${prefix}${b.value} (${b.count})` }))
  if (current && !options.some((o) => o.value === current)) {
    options.unshift({ value: current, label: `${prefix}${current}` })
  }
  return options
}

interface SelectProps {
  label: string
  value: string
  options: Option[]
  onChange: (value: string) => void
}

function FilterSelect({ label, value, options, onChange }: SelectProps) {
  return (
    <label className={value ? 'dv-field dv-field--set' : 'dv-field'}>
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">all</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function FilterBar(props: Props) {
  const { view, users, searchText, onSelect } = props
  const userOptions: Option[] = users.map((u) => ({
    value: String(u.id),
    label: `${u.email} (${u.task_count})`,
  }))
  if (view.user_id && !userOptions.some((o) => o.value === view.user_id)) {
    userOptions.unshift({ value: view.user_id, label: `user ${view.user_id}` })
  }
  const hasFilters =
    !!(view.user_id || view.status || view.priority || view.project || view.hashtag || view.q) ||
    view.include_deleted ||
    searchText !== ''

  return (
    <div className="dv-filters" role="search">
      <FilterSelect label="User" value={view.user_id} options={userOptions} onChange={(v) => onSelect('user_id', v)} />
      <FilterSelect
        label="Status"
        value={view.status}
        options={optionsFrom(props.statuses, view.status)}
        onChange={(v) => onSelect('status', v)}
      />
      <FilterSelect
        label="Priority"
        value={view.priority}
        options={optionsFrom(props.priorities, view.priority)}
        onChange={(v) => onSelect('priority', v)}
      />
      <FilterSelect
        label="Project"
        value={view.project}
        options={optionsFrom(props.projects, view.project)}
        onChange={(v) => onSelect('project', v)}
      />
      <FilterSelect
        label="#"
        value={view.hashtag}
        options={optionsFrom(props.hashtags, view.hashtag, '#')}
        onChange={(v) => onSelect('hashtag', v)}
      />
      <label className={searchText ? 'dv-field dv-field--grow dv-field--set' : 'dv-field dv-field--grow'}>
        <span aria-hidden="true">🔍</span>
        <input
          type="search"
          placeholder="Search title and notes"
          aria-label="Search title and notes"
          value={searchText}
          onChange={(e) => props.onSearchText(e.target.value)}
        />
      </label>
      <label className="dv-check">
        <input
          type="checkbox"
          checked={view.include_deleted}
          onChange={(e) => props.onIncludeDeleted(e.target.checked)}
        />
        <span>show deleted</span>
      </label>
      <button type="button" className="dv-button" onClick={props.onClear} disabled={!hasFilters}>
        Clear
      </button>
    </div>
  )
}
