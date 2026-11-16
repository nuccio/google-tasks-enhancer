"""Tests for the read-only dev UI API (backend/devui.py) and the /dev page."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend import devui, main, models
from backend.database import get_db
from backend.main import app

LOOPBACK_CLIENT = ("127.0.0.1", 50000)
LOCAL_BASE_URL = "http://localhost:8000"

API_PATHS = [
    "/dev/api/overview",
    "/dev/api/users",
    "/dev/api/tasks",
    "/dev/api/tasks/t001",
    "/dev/api/status",
]
GUARDED_PATHS = ["/dev", "/dev/"] + API_PATHS

SECRET_ACCESS = "ya29.SECRET-ACCESS-TOKEN-VALUE"
SECRET_REFRESH = "1//SECRET-REFRESH-TOKEN-VALUE"
SECRET_CLIENT = "SECRET-CLIENT-SECRET-VALUE"

STATUSES = ["needsAction", "completed"]
# The priority column defaults to "medium", so it is never NULL in practice
PRIORITIES = ["high", "medium", "low", "medium"]
PROJECTS = ["home", "work", None]
HASHTAGS = [["shop"], ["q4", "shop"], [], None]
TASK_COUNT = 150


@pytest.fixture
def make_client(db):
    """Build a TestClient on the test database with the given client address."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    def factory(client=LOOPBACK_CLIENT, base_url=LOCAL_BASE_URL):
        return TestClient(app, base_url=base_url, client=client)

    yield factory
    app.dependency_overrides.clear()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("DEV_UI_ENABLED", "true")


@pytest.fixture
def dev_client(make_client, enabled):
    return make_client()


def task_fields(i, owner_id):
    """Deterministic task data, used both to seed and to compute expectations."""
    title = f"Task {i:03d}"
    notes = None
    if i == 7:
        title = "Report 100% ready"
    elif i == 8:
        title = "report 100 ready"
    elif i == 9:
        notes = "a snake_case note"
    elif i == 10:
        notes = "a snakeXcase note"
    return {
        "id": f"t{i:03d}",
        "kind": "tasks#task",
        "etag": f"etag-{i}",
        "title": title,
        "notes": notes,
        "updated": f"2026-11-{(i % 28) + 1:02d}T10:{i % 60:02d}:00.000Z",
        "selfLink": f"https://example.invalid/tasks/t{i:03d}",
        "parent": None,
        "position": f"{i:020d}",
        "status": STATUSES[i % 2],
        "due_date": None if i % 5 == 0 else f"2026-12-{(i % 28) + 1:02d}T00:00:00.000Z",
        "completed": None,
        "deleted": i % 17 == 0,
        "hidden": i % 19 == 0,
        "webViewLink": None,
        "assignmentInfo": {"surface": "DOCUMENT"} if i == 1 else None,
        "links": [{"type": "email", "link": "https://example.invalid"}] if i == 1 else None,
        "tasklist_id": None if i % 23 == 0 else "list-1",
        "priority": PRIORITIES[i % 4],
        "project_name": PROJECTS[i % 3],
        "hashtags": HASHTAGS[i % 4],
        "estimated_time_minutes": i if i % 2 else None,
        "owner_id": owner_id,
    }


@pytest.fixture
def seeded(db):
    """Two users, one with Google tokens, and 150 tasks."""
    with_tokens = models.User(
        email="with-tokens@example.invalid",
        google_tokens={
            "access_token": SECRET_ACCESS,
            "refresh_token": SECRET_REFRESH,
            "client_secret": SECRET_CLIENT,
        },
    )
    without_tokens = models.User(email="no-tokens@example.invalid", google_tokens=None)
    never_set = models.User(email="never-set@example.invalid")
    db.add_all([with_tokens, without_tokens, never_set])
    db.commit()
    tasks = []
    for i in range(TASK_COUNT):
        owner = with_tokens.id if i < 100 else without_tokens.id
        data = task_fields(i, owner)
        tasks.append(data)
        db.add(models.Task(**data))
    db.commit()
    return SimpleNamespace(
        users=[with_tokens, without_tokens, never_set],
        tasks=tasks,
    )


def visible(tasks):
    return [t for t in tasks if not t["deleted"]]


def expected_order(tasks, column, order):
    """NULLs last in both directions, ties broken by id ascending."""
    by_id = sorted(tasks, key=lambda t: t["id"])
    present = [t for t in by_id if t[column] is not None]
    missing = [t for t in by_id if t[column] is None]
    present.sort(key=lambda t: t[column], reverse=(order == "desc"))
    return [t["id"] for t in present + missing]


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


# Guard: flag

@pytest.mark.parametrize("value", [None, "", "false", "0", "no", "off", "enabled"])
def test_disabled_flag_answers_404_everywhere(make_client, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DEV_UI_ENABLED", raising=False)
    else:
        monkeypatch.setenv("DEV_UI_ENABLED", value)
    client = make_client()
    for path in GUARDED_PATHS + ["/dev/api", "/dev/api/unknown", "/dev/api/tasks?sort=bogus"]:
        assert client.get(path).status_code == 404, path


def test_disabled_flag_is_checked_before_client_and_host(make_client, monkeypatch):
    monkeypatch.delenv("DEV_UI_ENABLED", raising=False)
    client = make_client(client=("203.0.113.5", 50000), base_url="http://evil.example")
    for path in GUARDED_PATHS:
        assert client.get(path).status_code == 404, path


@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE", "Yes", " true "])
def test_enabled_flag_values(make_client, monkeypatch, value):
    monkeypatch.setenv("DEV_UI_ENABLED", value)
    assert make_client().get("/dev/api/status").status_code == 200


def test_flag_is_read_at_request_time(make_client, monkeypatch):
    client = make_client()
    monkeypatch.delenv("DEV_UI_ENABLED", raising=False)
    assert client.get("/dev/api/status").status_code == 404
    monkeypatch.setenv("DEV_UI_ENABLED", "true")
    assert client.get("/dev/api/status").status_code == 200
    monkeypatch.setenv("DEV_UI_ENABLED", "false")
    assert client.get("/dev/api/status").status_code == 404


# Guard: client address

@pytest.mark.parametrize(
    "address",
    ["192.168.1.10", "10.0.0.1", "203.0.113.5", "::ffff:192.168.1.10", "2001:db8::1", "testclient", ""],
)
def test_non_loopback_client_answers_403(make_client, enabled, address):
    client = make_client(client=(address, 50000))
    for path in GUARDED_PATHS:
        assert client.get(path).status_code == 403, path


@pytest.mark.parametrize("address", ["127.0.0.1", "127.8.9.10", "::1", "::ffff:127.0.0.1"])
def test_loopback_clients_are_accepted(make_client, enabled, address):
    assert make_client(client=(address, 50000)).get("/dev/api/status").status_code == 200


def test_forwarded_for_is_ignored_without_proxy_headers_handling(make_client, enabled):
    """The guard reads the client address of the ASGI scope, not the header itself."""
    client = make_client()
    response = client.get("/dev/api/status", headers={"x-forwarded-for": "203.0.113.5"})
    assert response.status_code == 200
    client = make_client(client=("203.0.113.5", 50000))
    response = client.get("/dev/api/status", headers={"x-forwarded-for": "127.0.0.1"})
    assert response.status_code == 403


def uvicorn_client(client=LOOPBACK_CLIENT):
    """The app behind uvicorn's default proxy-headers handling (trusts 127.0.0.1)."""
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")
    return TestClient(proxied, base_url=LOCAL_BASE_URL, client=client)


@pytest.mark.parametrize(
    "forwarded", ["203.0.113.5", "192.168.1.10", "2001:db8::1", "127.0.0.1, 203.0.113.5"]
)
def test_forwarded_non_loopback_client_answers_403(make_client, enabled, forwarded):
    client = uvicorn_client()
    for path in GUARDED_PATHS:
        response = client.get(path, headers={"x-forwarded-for": forwarded})
        assert response.status_code == 403, path


def test_forwarded_loopback_client_is_accepted(make_client, enabled):
    response = uvicorn_client().get("/dev/api/status", headers={"x-forwarded-for": "127.0.0.1"})
    assert response.status_code == 200


def test_forwarded_for_from_untrusted_peer_is_not_used(make_client, enabled):
    client = uvicorn_client(client=("203.0.113.5", 50000))
    response = client.get("/dev/api/status", headers={"x-forwarded-for": "127.0.0.1"})
    assert response.status_code == 403


def test_non_loopback_client_answers_403_before_validation(make_client, enabled):
    client = make_client(client=("203.0.113.5", 50000))
    assert client.get("/dev/api/tasks?sort=bogus&limit=0").status_code == 403


# Guard: Host header

@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:8000",
        "localhost.evil.example",
        "127.0.0.1.nip.io",
        "testserver",
        "0.0.0.0:8000",
        "192.168.1.10:8000",
        "[::2]:8000",
        "::1",
        "localhost:",
        "localhost:abc",
        "localhost:8000:9000",
        "[::1",
        "[::1]x",
    ],
)
def test_non_local_host_answers_403(make_client, enabled, host):
    client = make_client()
    for path in GUARDED_PATHS:
        assert client.get(path, headers={"host": host}).status_code == 403, path


@pytest.mark.parametrize(
    "host",
    ["localhost", "localhost:8000", "LOCALHOST:5173", "127.0.0.1", "127.0.0.1:8000", "[::1]", "[::1]:8000"],
)
def test_local_hosts_are_accepted(make_client, enabled, host):
    response = make_client().get("/dev/api/status", headers={"host": host})
    assert response.status_code == 200


def test_missing_host_is_rejected():
    assert devui._host_is_local(None) is False
    assert devui._host_is_local("") is False


# Methods and unknown paths

def test_every_router_route_accepts_only_get():
    assert devui.router.routes
    for route in devui.router.routes:
        assert route.methods == {"GET"}, route.path


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_other_methods_are_not_allowed(dev_client, method):
    for path in API_PATHS:
        assert getattr(dev_client, method)(path).status_code == 405, path


def test_unknown_dev_api_path_is_404_not_the_app(dev_client):
    for path in ["/dev/api", "/dev/api/", "/dev/api/unknown", "/dev/api/tasks/a/b"]:
        response = dev_client.get(path)
        assert response.status_code == 404, path
        assert "text/html" not in response.headers.get("content-type", "")


def test_other_paths_still_reach_the_app_catch_all(dev_client):
    assert dev_client.get("/").status_code == 200
    assert dev_client.get("/developer").status_code == 200


# The /dev page

def test_dev_page_is_served_when_built(dev_client, monkeypatch, tmp_path):
    (tmp_path / "dev.html").write_text("<!doctype html><title>Data viewer</title>")
    monkeypatch.setattr(main, "STATIC_DIR", str(tmp_path))
    for path in ["/dev", "/dev/"]:
        response = dev_client.get(path)
        assert response.status_code == 200
        assert "Data viewer" in response.text


def test_dev_page_explains_when_not_built(dev_client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "STATIC_DIR", str(tmp_path))
    response = dev_client.get("/dev")
    assert response.status_code == 404
    assert "npm run build" in response.text


# Google tokens never leave the database

def test_no_response_contains_google_tokens(dev_client, seeded):
    paths = API_PATHS + [
        "/dev/api/tasks?include_deleted=true&limit=500",
        f"/dev/api/tasks?user_id={seeded.users[0].id}",
    ]
    for path in paths:
        response = dev_client.get(path)
        assert response.status_code == 200, path
        body = response.text
        assert '"google_tokens"' not in body, path
        for secret in (SECRET_ACCESS, SECRET_REFRESH, SECRET_CLIENT, "access_token", "refresh_token"):
            assert secret not in body, path


def test_users(dev_client, seeded):
    response = dev_client.get("/dev/api/users")
    assert response.status_code == 200
    with_tokens, without_tokens, never_set = seeded.users
    assert response.json() == [
        {"id": with_tokens.id, "email": with_tokens.email, "task_count": 100, "has_google_tokens": True},
        {"id": without_tokens.id, "email": without_tokens.email, "task_count": 50, "has_google_tokens": False},
        {"id": never_set.id, "email": never_set.email, "task_count": 0, "has_google_tokens": False},
    ]


# Tasks list

def test_tasks_default_hides_deleted_and_shows_hidden(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks", params={"limit": 500})
    expected = visible(seeded.tasks)
    assert response.json()["total"] == len(expected)
    assert set(ids(response)) == {t["id"] for t in expected}
    assert len(expected) > 100
    items = response.json()["items"]
    assert not any(item["deleted"] for item in items)
    assert any(item["hidden"] for item in items)
    hidden_not_deleted = {t["id"] for t in seeded.tasks if t["hidden"] and not t["deleted"]}
    assert hidden_not_deleted and hidden_not_deleted <= set(ids(response))


def test_tasks_default_page(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks")
    body = response.json()
    assert len(body["items"]) == 50
    assert ids(response) == expected_order(visible(seeded.tasks), "updated", "desc")[:50]


def test_tasks_default_treats_empty_deleted_as_false(dev_client, seeded, db):
    db.query(models.Task).filter(models.Task.id == "t017").update({"deleted": None})
    db.query(models.Task).filter(models.Task.id == "t019").update({"deleted": None, "hidden": True})
    db.commit()
    response = dev_client.get("/dev/api/tasks", params={"limit": 500})
    assert {"t017", "t019"} <= set(ids(response))


def test_tasks_include_deleted(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks", params={"include_deleted": "true", "limit": 500})
    assert response.json()["total"] == TASK_COUNT
    assert set(ids(response)) == {t["id"] for t in seeded.tasks}
    assert any(item["deleted"] for item in response.json()["items"])
    assert any(item["hidden"] for item in response.json()["items"])


@pytest.mark.parametrize(
    "param, column, value",
    [
        ("status", "status", "completed"),
        ("status", "status", "needsAction"),
        ("priority", "priority", "high"),
        ("priority", "priority", "low"),
        ("project", "project_name", "home"),
        ("project", "project_name", "work"),
    ],
)
def test_tasks_exact_filters(dev_client, seeded, param, column, value):
    response = dev_client.get("/dev/api/tasks", params={param: value, "limit": 500})
    expected = [t for t in visible(seeded.tasks) if t[column] == value]
    assert response.json()["total"] == len(expected)
    assert set(ids(response)) == {t["id"] for t in expected}


def test_tasks_user_filter(dev_client, seeded):
    for user in seeded.users:
        response = dev_client.get("/dev/api/tasks", params={"user_id": user.id, "limit": 500})
        expected = [t for t in visible(seeded.tasks) if t["owner_id"] == user.id]
        assert response.json()["total"] == len(expected)
        assert set(ids(response)) == {t["id"] for t in expected}


@pytest.mark.parametrize("value", ["shop", "#shop", "q4"])
def test_tasks_hashtag_filter(dev_client, seeded, value):
    response = dev_client.get("/dev/api/tasks", params={"hashtag": value, "limit": 500})
    tag = value.removeprefix("#")
    expected = [t for t in visible(seeded.tasks) if tag in (t["hashtags"] or [])]
    assert expected
    assert response.json()["total"] == len(expected)
    assert set(ids(response)) == {t["id"] for t in expected}


def test_tasks_hashtag_filter_without_matches(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks", params={"hashtag": "missing"})
    assert response.json() == {"total": 0, "items": []}


@pytest.mark.parametrize(
    "q, expected",
    [
        ("report", {"t007", "t008"}),
        ("REPORT 100", {"t007", "t008"}),
        ("100%", {"t007"}),
        ("e_c", {"t009"}),
        ("SNAKE", {"t009", "t010"}),
        ("%", {"t007"}),
        ("_", {"t009"}),
        ("no such text", set()),
    ],
)
def test_tasks_text_search(dev_client, seeded, q, expected):
    response = dev_client.get("/dev/api/tasks", params={"q": q, "limit": 500})
    assert response.json()["total"] == len(expected)
    assert set(ids(response)) == expected


def test_tasks_filters_combine(dev_client, seeded):
    params = {"status": "needsAction", "project": "home", "hashtag": "shop", "user_id": seeded.users[0].id}
    response = dev_client.get("/dev/api/tasks", params={**params, "limit": 500})
    expected = [
        t
        for t in visible(seeded.tasks)
        if t["status"] == "needsAction"
        and t["project_name"] == "home"
        and "shop" in (t["hashtags"] or [])
        and t["owner_id"] == seeded.users[0].id
    ]
    assert response.json()["total"] == len(expected)
    assert set(ids(response)) == {t["id"] for t in expected}


@pytest.mark.parametrize("sort", ["title", "updated", "due_date", "priority", "project_name", "status"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_tasks_sort(dev_client, seeded, sort, order):
    response = dev_client.get(
        "/dev/api/tasks", params={"sort": sort, "order": order, "include_deleted": "true", "limit": 500}
    )
    assert ids(response) == expected_order(seeded.tasks, sort, order)


def test_tasks_pagination(dev_client, seeded):
    expected = expected_order(visible(seeded.tasks), "title", "asc")
    pages = []
    for offset in range(0, len(expected) + 40, 40):
        response = dev_client.get(
            "/dev/api/tasks", params={"sort": "title", "order": "asc", "limit": 40, "offset": offset}
        )
        assert response.json()["total"] == len(expected)
        page = ids(response)
        assert len(page) <= 40
        pages.extend(page)
    assert pages == expected
    response = dev_client.get("/dev/api/tasks", params={"offset": len(expected)})
    assert response.json() == {"total": len(expected), "items": []}


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "bogus"},
        {"sort": "notes"},
        {"sort": "owner_id"},
        {"order": "up"},
        {"limit": 0},
        {"limit": 501},
        {"offset": -1},
        {"user_id": "abc"},
        {"user_id": 2**63},
        {"user_id": 10**40},
        {"offset": 2**63},
        {"offset": 10**40},
    ],
)
def test_tasks_invalid_parameters_answer_422(dev_client, seeded, params):
    assert dev_client.get("/dev/api/tasks", params=params).status_code == 422


def test_tasks_limit_bounds(dev_client, seeded):
    assert len(dev_client.get("/dev/api/tasks", params={"limit": 1}).json()["items"]) == 1
    response = dev_client.get("/dev/api/tasks", params={"limit": 500, "include_deleted": "true"})
    assert len(response.json()["items"]) == TASK_COUNT


def test_tasks_largest_sqlite_integer_is_accepted(dev_client, seeded):
    largest = 2**63 - 1
    for params in ({"user_id": largest}, {"offset": largest}):
        response = dev_client.get("/dev/api/tasks", params=params)
        assert response.status_code == 200, params
        assert response.json()["items"] == []


def test_task_summary_fields(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks", params={"limit": 1})
    item = response.json()["items"][0]
    assert set(item) == set(devui.TaskSummary.model_fields)


# Task detail

def test_task_detail_has_every_column(dev_client, seeded):
    response = dev_client.get("/dev/api/tasks/t001")
    assert response.status_code == 200
    columns = {column.name for column in models.Task.__table__.columns}
    assert set(response.json()) == columns
    assert response.json() == seeded.tasks[1]


def test_task_detail_unknown_id(dev_client, seeded):
    assert dev_client.get("/dev/api/tasks/missing").status_code == 404


# Overview

def count_by(tasks, column):
    counts = {}
    for t in tasks:
        counts[t[column]] = counts.get(t[column], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0] is not None, kv[0] or ""))
    return [{"value": value, "count": n} for value, n in ordered]


def test_overview(dev_client, seeded):
    response = dev_client.get("/dev/api/overview")
    assert response.status_code == 200
    body = response.json()
    tasks = seeded.tasks
    assert body["users"] == 3
    assert body["tasks"] == TASK_COUNT
    assert body["deleted"] == sum(t["deleted"] for t in tasks)
    assert body["hidden"] == sum(t["hidden"] for t in tasks)
    assert body["without_tasklist_id"] == sum(t["tasklist_id"] is None for t in tasks)
    assert body["without_due_date"] == sum(t["due_date"] is None for t in tasks)
    assert body["last_updated"] == max(t["updated"] for t in tasks)
    for key, column in [("by_status", "status"), ("by_priority", "priority"), ("by_project_name", "project_name")]:
        assert sorted(body[key], key=lambda c: (c["value"] or "", c["count"])) == sorted(
            count_by(tasks, column), key=lambda c: (c["value"] or "", c["count"])
        ), key
        counts = [c["count"] for c in body[key]]
        assert counts == sorted(counts, reverse=True), key
    shop = sum("shop" in (t["hashtags"] or []) for t in tasks)
    q4 = sum("q4" in (t["hashtags"] or []) for t in tasks)
    assert body["by_hashtag"] == [{"value": "shop", "count": shop}, {"value": "q4", "count": q4}]


def test_overview_hashtags_top_20(dev_client, db):
    user = models.User(email="u@example.invalid")
    db.add(user)
    db.commit()
    for i in range(25):
        # tag-00 appears in 26 tasks, tag-01 in 25, ... ; one task lists a tag twice
        tags = [f"tag-{j:02d}" for j in range(i + 1)]
        db.add(models.Task(id=f"h{i:02d}", title="x", hashtags=tags, owner_id=user.id))
    db.add(models.Task(id="dup", title="x", hashtags=["tag-00", "tag-00"], owner_id=user.id))
    db.commit()
    body = dev_client.get("/dev/api/overview").json()
    assert len(body["by_hashtag"]) == 20
    assert body["by_hashtag"][0] == {"value": "tag-00", "count": 26}
    assert body["by_hashtag"][1] == {"value": "tag-01", "count": 24}
    assert [c["value"] for c in body["by_hashtag"]] == [f"tag-{j:02d}" for j in range(20)]


def test_overview_empty_database(dev_client):
    body = dev_client.get("/dev/api/overview").json()
    assert body == {
        "users": 0,
        "tasks": 0,
        "deleted": 0,
        "hidden": 0,
        "without_tasklist_id": 0,
        "without_due_date": 0,
        "last_updated": None,
        "by_status": [],
        "by_priority": [],
        "by_project_name": [],
        "by_hashtag": [],
    }


# Status

def test_status_without_alembic_table(dev_client):
    body = dev_client.get("/dev/api/status").json()
    assert body["alembic_revision"] == "unknown"
    assert isinstance(body["scheduler_running"], bool)
    assert isinstance(body["jobs"], list)


def test_status_reads_alembic_revision(dev_client, db):
    db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
    db.execute(text("INSERT INTO alembic_version (version_num) VALUES ('a1b2c3d4')"))
    db.commit()
    try:
        assert dev_client.get("/dev/api/status").json()["alembic_revision"] == "a1b2c3d4"
    finally:
        db.execute(text("DROP TABLE alembic_version"))
        db.commit()


def test_status_reports_scheduler_jobs_without_changing_them(dev_client):
    next_run = datetime(2026, 11, 15, 12, 30, tzinfo=timezone.utc)
    fake = MagicMock()
    fake.running = True
    fake.get_jobs.return_value = [
        SimpleNamespace(id="sync_user_1", next_run_time=next_run),
        SimpleNamespace(id="pending_job"),
    ]
    with patch.object(devui.scheduler, "scheduler", fake):
        body = dev_client.get("/dev/api/status").json()
    assert body["scheduler_running"] is True
    assert body["jobs"] == [
        {"id": "sync_user_1", "next_run_time": "2026-11-15T12:30:00Z"},
        {"id": "pending_job", "next_run_time": None},
    ]
    assert [c[0] for c in fake.method_calls] == ["get_jobs"]


# Read only

def test_requests_do_not_write_to_the_database(dev_client, seeded, db):
    with patch.object(db, "commit", side_effect=AssertionError("commit called")), \
         patch.object(db, "add", side_effect=AssertionError("add called")):
        for path in API_PATHS + ["/dev/api/tasks?include_deleted=true&hashtag=shop&q=x"]:
            assert dev_client.get(path).status_code == 200, path
