import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.middleware.sessions import SessionMiddleware

from backend import crud, models


def _session_cookie(app, session: dict) -> str:
    """Sign a session cookie with the key of the app's own SessionMiddleware."""
    layer = app.middleware_stack
    while layer is not None and not isinstance(layer, SessionMiddleware):
        layer = getattr(layer, "app", None)
    assert layer is not None, "SessionMiddleware not found in the middleware stack"
    payload = base64.b64encode(json.dumps(session).encode("utf-8"))
    return layer.signer.sign(payload).decode("utf-8")


@pytest.fixture
def user(db):
    # The sync closes the session, which detaches ORM objects: keep only the ID
    created = crud.create_user(db, email="tasks@example.com", google_tokens={"access_token": "valid"})
    return SimpleNamespace(id=created.id, email=created.email)


@pytest.fixture
def logged_in_client(client, user):
    client.cookies.set("session", _session_cookie(client.app, {"user": {"email": "tasks@example.com"}}))
    return client


# --- GET /tasks/ (D5) ---

def test_get_tasks_returns_every_task_with_no_row_cap(logged_in_client, db, user):
    for i in range(370):
        db.add(models.Task(id=f"t{i}", title=f"T{i}", status="needsAction", owner_id=user.id))
    db.commit()

    response = logged_in_client.get("/tasks/")

    assert response.status_code == 200
    assert len(response.json()) == 370


def test_get_tasks_leaves_out_deleted_tasks(logged_in_client, db, user):
    db.add_all([
        models.Task(id="open", title="Open", status="needsAction", deleted=False, owner_id=user.id),
        models.Task(id="gone", title="Gone", status="needsAction", deleted=True, owner_id=user.id),
        models.Task(id="unset", title="Unset", status="needsAction", deleted=None, owner_id=user.id),
    ])
    db.commit()

    response = logged_in_client.get("/tasks/")

    assert sorted(t["id"] for t in response.json()) == ["open", "unset"]


def test_get_tasks_returns_hidden_completed_tasks_with_the_same_fields(logged_in_client, db, user):
    db.add(models.Task(
        id="t1", title="T", status="completed", completed="2026-01-01T10:00:00.000Z", hidden=True,
        tasklist_id="list1", priority="high", project_name="Home", hashtags=["a"],
        estimated_time_minutes=20, owner_id=user.id,
    ))
    db.commit()

    [task] = logged_in_client.get("/tasks/").json()

    assert task["status"] == "completed"
    assert task["hidden"] is True
    assert {"id", "title", "status", "due_date", "completed", "priority", "project_name",
            "hashtags", "estimated_time_minutes", "tasklist_id", "deleted", "hidden"} <= set(task)


def test_get_tasks_returns_only_the_tasks_of_the_logged_in_user(logged_in_client, db, user):
    other = crud.create_user(db, email="other@example.com", google_tokens={"access_token": "x"})
    db.add_all([
        models.Task(id="mine", title="Mine", owner_id=user.id),
        models.Task(id="theirs", title="Theirs", owner_id=other.id),
    ])
    db.commit()

    assert [t["id"] for t in logged_in_client.get("/tasks/").json()] == ["mine"]


def test_get_user_tasks_include_deleted(db, user):
    db.add_all([
        models.Task(id="open", title="Open", deleted=False, owner_id=user.id),
        models.Task(id="gone", title="Gone", deleted=True, owner_id=user.id),
    ])
    db.commit()

    assert [t.id for t in crud.get_user_tasks(db, user.id)] == ["open"]
    assert sorted(t.id for t in crud.get_user_tasks(db, user.id, include_deleted=True)) == ["gone", "open"]


# --- PATCH /tasks/{id} (D8) ---

def test_patch_reopening_a_task_empties_completed_and_keeps_custom_fields(logged_in_client, db, user):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T #old", "status": "completed", "completed": "2026-01-01T10:00:00.000Z",
        "hidden": True, "tasklist_id": "list1", "priority": "high", "project_name": "Home",
        "estimated_time_minutes": 45,
    }, user_id=user.id)
    # What Google answers to the reopen: no 'completed', no 'hidden', 'due' instead of 'due_date'
    google_reply = {
        "kind": "tasks#task", "id": "t1", "etag": "new-etag", "title": "T #old", "status": "needsAction",
        "updated": "2026-01-02T00:00:00.000Z", "due": "2026-02-01T00:00:00.000Z", "unknownField": "x",
    }

    with patch("backend.main.scheduler.update_task_status_on_google", return_value=google_reply):
        response = logged_in_client.patch("/tasks/t1", json={"status": "needsAction"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needsAction"
    assert body["completed"] is None
    assert body["hidden"] is False
    assert body["due_date"] == "2026-02-01T00:00:00.000Z"
    assert body["etag"] == "new-etag"
    assert body["hashtags"] == ["old"]
    assert (body["priority"], body["project_name"], body["estimated_time_minutes"]) == ("high", "Home", 45)
    assert body["tasklist_id"] == "list1"
    assert "unknownField" not in body


def test_patch_completing_a_task_stores_completed_as_google_sent_it(logged_in_client, db, user):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T", "status": "needsAction", "tasklist_id": "list1", "priority": "low",
    }, user_id=user.id)
    google_reply = {"id": "t1", "title": "T", "status": "completed", "completed": "2026-03-01T08:00:00.000Z"}

    with patch("backend.main.scheduler.update_task_status_on_google", return_value=google_reply):
        response = logged_in_client.patch("/tasks/t1", json={"status": "completed"})

    assert response.status_code == 200
    assert response.json()["completed"] == "2026-03-01T08:00:00.000Z"
    assert response.json()["priority"] == "low"


def test_patch_custom_fields_without_status_change_does_not_call_google(logged_in_client, db, user):
    crud.create_or_update_task(db, {"id": "t1", "title": "T", "status": "needsAction"}, user_id=user.id)

    with patch("backend.main.scheduler.update_task_status_on_google") as google:
        response = logged_in_client.patch("/tasks/t1", json={"priority": "high", "project_name": "P"})

    assert response.status_code == 200
    google.assert_not_called()
    assert response.json()["priority"] == "high"
    assert response.json()["project_name"] == "P"


# --- GET /tasks/ after a sync, through the whole stack ---

def test_sync_then_get_tasks_returns_all_tasks_with_googles_status(logged_in_client, db, user):
    from backend.tests.test_scheduler import FakeGoogle

    big = [{"id": f"a{i}", "title": f"T{i}", "status": "needsAction"} for i in range(250)]
    small = [{"id": f"b{i}", "title": f"T{i}", "status": "completed", "hidden": True,
              "completed": "2026-01-01T10:00:00.000Z"} for i in range(120)]
    google = FakeGoogle(
        tasklists=[[{"id": "listA", "title": "A"}], [{"id": "listB", "title": "B"}]],
        tasks={
            "listA": [big[:100], big[100:200], big[200:]],
            "listB": [small[:100], small[100:]],
        },
    )

    with patch("backend.scheduler.get_google_tasks_service", return_value=google), \
         patch("backend.scheduler.SessionLocal", return_value=db):
        response = logged_in_client.post("/tasks/sync")
    assert response.status_code == 200

    tasks = logged_in_client.get("/tasks/").json()
    assert len(tasks) == 370
    assert sum(t["status"] == "completed" for t in tasks) == 120
