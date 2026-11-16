"""Read-only data viewer API for local development.

Every route answers 404 unless ``DEV_UI_ENABLED`` is on, and 403 unless the
request comes from a loopback address with a local ``Host`` header. The routes
only read the database: they never commit, never call Google and never start,
stop or change scheduler jobs. Responses use explicit models, so columns such
as ``users.google_tokens`` cannot reach a response by accident. Nothing here
logs task titles, notes or emails.
"""

import ipaddress
import os
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import String, and_, case, cast, false, func, inspect, or_, select, text, true
from sqlalchemy.orm import Session

from . import database, models, scheduler

DEV_UI_FLAG = "DEV_UI_ENABLED"
_TRUE_VALUES = {"true", "1", "yes"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
# Largest SQLite integer: bigger query values answer 422 instead of failing in the driver.
SQLITE_INT_MAX = 2**63 - 1


def dev_ui_enabled() -> bool:
    """Read the flag at request time, so it can change without a restart."""
    return os.getenv(DEV_UI_FLAG, "").strip().lower() in _TRUE_VALUES


def _client_is_loopback(request: Request) -> bool:
    if request.client is None or not request.client.host:
        return False
    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def _host_is_local(host: Optional[str]) -> bool:
    """True for localhost, 127.0.0.1 or [::1], with or without a port."""
    if not host:
        return False
    host = host.strip().lower()
    if host.startswith("["):
        end = host.find("]")
        if end == -1:
            return False
        name, rest = host[: end + 1], host[end + 1 :]
    else:
        name, separator, port = host.partition(":")
        rest = separator + port
    if rest and not (rest.startswith(":") and rest[1:].isdigit()):
        return False
    return name in _LOCAL_HOSTS


def require_dev_access(request: Request) -> None:
    """Guard shared by the /dev page and every /dev/api route."""
    if not dev_ui_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    if not _client_is_loopback(request):
        raise HTTPException(status_code=403, detail="The dev UI only answers loopback clients")
    if not _host_is_local(request.headers.get("host")):
        raise HTTPException(status_code=403, detail="The dev UI only answers a local Host header")


router = APIRouter(
    prefix="/dev/api",
    tags=["Dev UI"],
    dependencies=[Depends(require_dev_access)],
)


# Response models: every field is listed by hand.

class CountItem(BaseModel):
    value: Optional[str]
    count: int


class OverviewOut(BaseModel):
    users: int
    tasks: int
    deleted: int
    hidden: int
    without_tasklist_id: int
    without_due_date: int
    last_updated: Optional[str]
    by_status: list[CountItem]
    by_priority: list[CountItem]
    by_project_name: list[CountItem]
    by_hashtag: list[CountItem]


class UserOut(BaseModel):
    id: int
    email: str
    task_count: int
    has_google_tokens: bool


class TaskSummary(BaseModel):
    id: str
    title: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    project_name: Optional[str]
    hashtags: Optional[list[str]]
    due_date: Optional[str]
    updated: Optional[str]
    completed: Optional[str]
    deleted: Optional[bool]
    hidden: Optional[bool]
    estimated_time_minutes: Optional[int]
    tasklist_id: Optional[str]
    owner_id: Optional[int]


class TaskPage(BaseModel):
    total: int
    items: list[TaskSummary]


class TaskDetail(BaseModel):
    id: str
    kind: Optional[str]
    etag: Optional[str]
    title: Optional[str]
    updated: Optional[str]
    selfLink: Optional[str]
    parent: Optional[str]
    position: Optional[str]
    notes: Optional[str]
    status: Optional[str]
    due_date: Optional[str]
    completed: Optional[str]
    deleted: Optional[bool]
    hidden: Optional[bool]
    webViewLink: Optional[str]
    assignmentInfo: Optional[Any]
    links: Optional[Any]
    tasklist_id: Optional[str]
    priority: Optional[str]
    project_name: Optional[str]
    hashtags: Optional[list[str]]
    estimated_time_minutes: Optional[int]
    owner_id: Optional[int]


class JobOut(BaseModel):
    id: str
    next_run_time: Optional[datetime]


class StatusOut(BaseModel):
    alembic_revision: str
    scheduler_running: bool
    jobs: list[JobOut]


# Query helpers.

Task = models.Task
User = models.User

_SUMMARY_COLUMNS = [getattr(Task, name) for name in TaskSummary.model_fields]
_DETAIL_COLUMNS = [getattr(Task, name) for name in TaskDetail.model_fields]

_SORT_COLUMNS = {
    "title": Task.title,
    "updated": Task.updated,
    "due_date": Task.due_date,
    "priority": Task.priority,
    "project_name": Task.project_name,
    "status": Task.status,
}
SortColumn = Literal["title", "updated", "due_date", "priority", "project_name", "status"]


def _hashtags():
    """Rows of SQLite's json_each over tasks.hashtags, one per hashtag."""
    return func.json_each(Task.hashtags).table_valued("value").alias("tag")


def _is_true(column):
    return column == true()


def _is_not_true(column):
    return or_(column.is_(None), column == false())


def _is_empty(column):
    return or_(column.is_(None), column == "")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _counts_by(db: Session, column) -> list[CountItem]:
    count = func.count(Task.id)
    rows = db.execute(
        select(column, count).group_by(column).order_by(count.desc(), column.asc())
    ).all()
    return [CountItem(value=value, count=n) for value, n in rows]


# Routes.

@router.get("/overview", response_model=OverviewOut)
def get_overview(db: Session = Depends(database.get_db)):
    users = db.execute(select(func.count(User.id))).scalar_one()
    totals = db.execute(
        select(
            func.count(Task.id),
            func.coalesce(func.sum(case((_is_true(Task.deleted), 1), else_=0)), 0),
            func.coalesce(func.sum(case((_is_true(Task.hidden), 1), else_=0)), 0),
            func.coalesce(func.sum(case((_is_empty(Task.tasklist_id), 1), else_=0)), 0),
            func.coalesce(func.sum(case((_is_empty(Task.due_date), 1), else_=0)), 0),
            func.max(Task.updated),
        )
    ).one()

    tag = _hashtags()
    tag_count = func.count(func.distinct(Task.id))
    hashtag_rows = db.execute(
        select(tag.c.value, tag_count)
        .select_from(Task)
        .join(tag, true())
        .where(tag.c.value.is_not(None))
        .group_by(tag.c.value)
        .order_by(tag_count.desc(), tag.c.value.asc())
        .limit(20)
    ).all()

    return OverviewOut(
        users=users,
        tasks=totals[0],
        deleted=totals[1],
        hidden=totals[2],
        without_tasklist_id=totals[3],
        without_due_date=totals[4],
        last_updated=totals[5],
        by_status=_counts_by(db, Task.status),
        by_priority=_counts_by(db, Task.priority),
        by_project_name=_counts_by(db, Task.project_name),
        by_hashtag=[CountItem(value=str(value), count=n) for value, n in hashtag_rows],
    )


@router.get("/users", response_model=list[UserOut])
def get_users(db: Session = Depends(database.get_db)):
    # google_tokens is only tested for presence; its value is never selected.
    has_tokens = and_(
        User.google_tokens.is_not(None),
        cast(User.google_tokens, String) != "null",
    )
    rows = db.execute(
        select(
            User.id,
            User.email,
            func.count(Task.id).label("task_count"),
            func.max(case((has_tokens, 1), else_=0)).label("has_google_tokens"),
        )
        .outerjoin(Task, Task.owner_id == User.id)
        .group_by(User.id, User.email)
        .order_by(User.id)
    ).all()
    return [
        UserOut(
            id=row.id,
            email=row.email,
            task_count=row.task_count,
            has_google_tokens=bool(row.has_google_tokens),
        )
        for row in rows
    ]


@router.get("/tasks", response_model=TaskPage)
def get_tasks(
    db: Session = Depends(database.get_db),
    user_id: Optional[int] = Query(None, le=SQLITE_INT_MAX),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    project: Optional[str] = None,
    hashtag: Optional[str] = None,
    q: Optional[str] = None,
    include_deleted: bool = False,
    sort: SortColumn = "updated",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=SQLITE_INT_MAX),
):
    conditions = []
    if user_id is not None:
        conditions.append(Task.owner_id == user_id)
    if status is not None:
        conditions.append(Task.status == status)
    if priority is not None:
        conditions.append(Task.priority == priority)
    if project is not None:
        conditions.append(Task.project_name == project)
    if hashtag is not None:
        tag = _hashtags()
        conditions.append(
            select(tag.c.value).where(tag.c.value == hashtag.removeprefix("#")).exists()
        )
    if q:
        pattern = f"%{_escape_like(q)}%"
        conditions.append(
            or_(
                Task.title.ilike(pattern, escape="\\"),
                Task.notes.ilike(pattern, escape="\\"),
            )
        )
    if not include_deleted:
        conditions.append(_is_not_true(Task.deleted))

    total = db.execute(select(func.count(Task.id)).where(*conditions)).scalar_one()

    column = _SORT_COLUMNS[sort]
    ordering = column.asc() if order == "asc" else column.desc()
    rows = db.execute(
        select(*_SUMMARY_COLUMNS)
        .where(*conditions)
        .order_by(ordering.nulls_last(), Task.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return TaskPage(
        total=total,
        items=[TaskSummary.model_validate(dict(row._mapping)) for row in rows],
    )


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, db: Session = Depends(database.get_db)):
    row = db.execute(select(*_DETAIL_COLUMNS).where(Task.id == task_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetail.model_validate(dict(row._mapping))


@router.get("/status", response_model=StatusOut)
def get_status(db: Session = Depends(database.get_db)):
    revision = "unknown"
    if inspect(db.connection()).has_table("alembic_version"):
        versions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if versions:
            revision = ",".join(sorted(versions))

    # Read only: the scheduler is inspected, never started, stopped or changed.
    background = scheduler.scheduler
    jobs = [
        JobOut(id=job.id, next_run_time=getattr(job, "next_run_time", None))
        for job in background.get_jobs()
    ]
    return StatusOut(
        alembic_revision=revision,
        scheduler_running=bool(background.running),
        jobs=jobs,
    )
