import traceback
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from backend import scheduler, models, crud


def test_extract_hashtags():
    assert scheduler.extract_hashtags("Buy milk #home #shopping") == ["home", "shopping"]
    assert scheduler.extract_hashtags("No hashtag") == []
    assert scheduler.extract_hashtags("#start hashtag") == ["start"]


class FakeGoogle:
    """
    A stand-in for the Google Tasks service. Every call is recorded.

    tasklists: list of pages, each a list of task list dicts.
    tasks: {list ID: list of pages}, each page a list of task dicts.
    fail_on: (list ID, page index) at which tasks.list raises.
    """

    def __init__(self, tasklists, tasks, fail_on=None):
        self.tasklists_pages = tasklists
        self.tasks_pages = tasks
        self.fail_on = fail_on
        self.tasklists_calls = []
        self.tasks_calls = []

    @staticmethod
    def _page_index(token):
        return int(token) if token else 0

    @staticmethod
    def _response(pages, index):
        response = {"items": pages[index]}
        if index + 1 < len(pages):
            response["nextPageToken"] = str(index + 1)
        return response

    def tasklists(self):
        outer = self

        class _Lists:
            def list(self, **kwargs):
                outer.tasklists_calls.append(kwargs)
                request = MagicMock()
                request.execute.side_effect = lambda: outer._response(
                    outer.tasklists_pages, outer._page_index(kwargs.get("pageToken"))
                )
                return request

        return _Lists()

    def tasks(self):
        outer = self

        class _Tasks:
            def list(self, **kwargs):
                outer.tasks_calls.append(kwargs)
                index = outer._page_index(kwargs.get("pageToken"))

                def execute():
                    if outer.fail_on == (kwargs["tasklist"], index):
                        raise RuntimeError("Google is down")
                    return outer._response(outer.tasks_pages[kwargs["tasklist"]], index)

                request = MagicMock()
                request.execute.side_effect = execute
                return request

        return _Tasks()


@pytest.fixture
def user(db):
    # The sync closes the session, which detaches ORM objects: keep only the ID
    created = crud.create_user(db, email="sync@example.com", google_tokens={"access_token": "valid"})
    return SimpleNamespace(id=created.id, email=created.email)


@pytest.fixture
def run_sync(db, user):
    """Runs sync_tasks_for_user against a FakeGoogle with the test database."""

    def _run(google):
        with patch("backend.scheduler.get_google_tasks_service", return_value=google), \
             patch("backend.scheduler.SessionLocal", return_value=db):
            scheduler.sync_tasks_for_user(user.id)

    return _run


def single_list(tasks, list_id="list1"):
    """A FakeGoogle with one list and one page of tasks."""
    return FakeGoogle([[{"id": list_id, "title": "Private list title"}]], {list_id: [tasks]})


def stored(db, user, task_id):
    db.expire_all()
    return crud.get_task(db, task_id, user.id)


def test_sync_tasks_for_user(db, user, run_sync):
    run_sync(single_list([{"id": "gtask1", "title": "Task from Google #work", "status": "needsAction"}]))

    tasks = crud.get_tasks(db, user_id=user.id)
    assert len(tasks) == 1
    assert tasks[0].id == "gtask1"
    assert tasks[0].hashtags == ["work"]
    assert tasks[0].priority == models.DEFAULT_PRIORITY
    assert tasks[0].project_name is None
    assert tasks[0].estimated_time_minutes is None
    assert tasks[0].tasklist_id == "list1"


# --- Field ownership (D1) ---

def test_sync_never_changes_custom_fields_of_an_existing_task(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "Old title #old", "status": "needsAction", "tasklist_id": "list1",
        "priority": "high", "project_name": "Home", "estimated_time_minutes": 30,
    }, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "New title #new", "status": "needsAction"}]))

    task = stored(db, user, "t1")
    assert task.title == "New title #new"
    assert task.hashtags == ["new"]
    assert task.priority == "high"
    assert task.project_name == "Home"
    assert task.estimated_time_minutes == 30


def test_sync_ignores_custom_fields_sent_by_google(db, user, run_sync):
    run_sync(single_list([{"id": "t1", "title": "T", "priority": "high", "project_name": "X"}]))

    task = stored(db, user, "t1")
    assert task.priority == models.DEFAULT_PRIORITY
    assert task.project_name is None


def test_missing_google_fields_are_stored_empty(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T", "status": "needsAction", "notes": "old notes",
        "due_date": "2026-01-01T00:00:00.000Z", "parent": "p1", "hidden": True, "deleted": True,
        "completed": "2025-12-31T10:00:00.000Z", "links": [{"type": "email"}],
        "assignmentInfo": {"surfaceType": "DOCUMENT"},
    }, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "T", "status": "needsAction"}]))

    task = stored(db, user, "t1")
    assert task.notes is None
    assert task.due_date is None
    assert task.parent is None
    assert task.completed is None
    assert task.links is None
    assert task.assignmentInfo is None
    assert task.hidden is False
    assert task.deleted is False


def test_due_is_stored_as_due_date(db, user, run_sync):
    run_sync(single_list([{"id": "t1", "title": "T", "due": "2026-03-04T00:00:00.000Z"}]))
    assert stored(db, user, "t1").due_date == "2026-03-04T00:00:00.000Z"


def test_reopened_task_loses_completed(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T", "status": "completed", "completed": "2026-01-01T10:00:00.000Z",
    }, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "T", "status": "needsAction"}]))

    task = stored(db, user, "t1")
    assert task.status == "needsAction"
    assert task.completed is None


def test_completed_is_stored_exactly_as_google_sent_it(db, user, run_sync):
    run_sync(single_list([
        {"id": "t1", "title": "T", "status": "completed", "completed": "2026-01-01T10:00:00.000Z"},
    ]))
    assert stored(db, user, "t1").completed == "2026-01-01T10:00:00.000Z"


def test_sync_never_writes_its_own_completed_timestamp(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "gone", "title": "Gone", "status": "needsAction"}, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "T", "status": "needsAction"}]))

    assert stored(db, user, "gone").completed is None
    assert stored(db, user, "t1").completed is None


def test_unknown_google_field_is_ignored(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "old", "title": "Old"}, user_id=user.id)

    run_sync(single_list([
        {"id": "new", "title": "New", "status": "needsAction", "newField": "x"},
        {"id": "old", "title": "Old", "status": "needsAction", "anotherField": {"a": 1}},
    ]))

    assert stored(db, user, "new").title == "New"
    assert not hasattr(stored(db, user, "new"), "newField")
    assert stored(db, user, "old").status == "needsAction"


def test_field_lists_cover_the_model_columns():
    columns = {c.name for c in models.Task.__table__.columns}
    owned = (
        set(scheduler.GOOGLE_FIELDS)
        | set(scheduler.SYNC_FIELDS)
        | set(scheduler.DERIVED_FIELDS)
        | set(scheduler.CUSTOM_FIELDS)
    )
    # 'id' is the key and 'owner_id' the user's: neither comes from a Google field
    assert owned | {"id", "owner_id"} == columns
    assert not owned & {"id", "owner_id"}
    # A column has one owner
    all_columns = [
        *scheduler.GOOGLE_FIELDS, *scheduler.SYNC_FIELDS, *scheduler.DERIVED_FIELDS, *scheduler.CUSTOM_FIELDS,
    ]
    assert len(all_columns) == len(set(all_columns))


# --- Every page (section 4) ---

def make_tasks(prefix, count, **extra):
    return [{"id": f"{prefix}{i}", "title": f"T {prefix}{i}", "status": "needsAction", **extra} for i in range(count)]


def chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def test_every_page_of_lists_and_tasks_is_read(db, user, run_sync):
    big = make_tasks("a", 250)
    for task in big[::2]:
        task["status"] = "completed"
        task["completed"] = "2026-01-01T10:00:00.000Z"
    small = make_tasks("b", 120)
    google = FakeGoogle(
        tasklists=[[{"id": "listA", "title": "A"}], [{"id": "listB", "title": "B"}]],
        tasks={"listA": chunks(big, 100), "listB": chunks(small, 100)},
    )

    run_sync(google)

    # The lists: two pages, the second one asked with the token of the first
    assert [c.get("pageToken") for c in google.tasklists_calls] == [None, "1"]
    assert all(c["maxResults"] == 1000 for c in google.tasklists_calls)
    # The tasks: pages of 100 with the flags, each page with the token of the previous one
    by_list = {}
    for call in google.tasks_calls:
        by_list.setdefault(call["tasklist"], []).append(call)
        assert call["maxResults"] == 100
        assert call["showCompleted"] is True
        assert call["showHidden"] is True
        assert call["showDeleted"] is True
        assert not call.get("showAssigned")
    assert [c.get("pageToken") for c in by_list["listA"]] == [None, "1", "2"]
    assert [c.get("pageToken") for c in by_list["listB"]] == [None, "1"]

    tasks = {t.id: t for t in crud.get_user_tasks(db, user.id)}
    assert len(tasks) == 370
    assert all(t.deleted is False for t in tasks.values())
    for i in range(250):
        expected = "completed" if i % 2 == 0 else "needsAction"
        assert tasks[f"a{i}"].status == expected
        assert tasks[f"a{i}"].tasklist_id == "listA"
    assert all(tasks[f"b{i}"].status == "needsAction" for i in range(120))
    assert all(tasks[f"b{i}"].tasklist_id == "listB" for i in range(120))


# --- Hidden, deleted (section 6, D4) ---

def test_hidden_completed_task_is_stored_completed(db, user, run_sync):
    run_sync(single_list([
        {"id": "t1", "title": "T", "status": "completed", "hidden": True, "completed": "2026-01-01T10:00:00.000Z"},
    ]))

    task = stored(db, user, "t1")
    assert task.status == "completed"
    assert task.hidden is True
    assert [t.id for t in crud.get_user_tasks(db, user.id)] == ["t1"]


def test_task_deleted_on_google_is_stored_deleted(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "t1", "title": "T", "status": "needsAction"}, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "T", "status": "needsAction", "deleted": True}]))

    assert stored(db, user, "t1").deleted is True
    assert crud.get_user_tasks(db, user.id) == []


def test_task_that_arrives_deleted_and_was_never_stored_is_not_added(db, user, run_sync):
    run_sync(single_list([
        {"id": "dead", "title": "Dead", "status": "needsAction", "deleted": True},
        {"id": "alive", "title": "Alive", "status": "needsAction"},
    ]))

    assert stored(db, user, "dead") is None
    assert stored(db, user, "alive") is not None


# --- Tasks Google no longer returns (D2) ---

def test_task_missing_from_its_list_is_marked_deleted_with_custom_fields_kept(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "gone", "title": "Gone", "status": "needsAction", "tasklist_id": "list1",
        "priority": "high", "project_name": "Home", "estimated_time_minutes": 15,
    }, user_id=user.id)

    run_sync(single_list([{"id": "other", "title": "Other", "status": "needsAction"}]))

    task = stored(db, user, "gone")
    assert task.deleted is True
    assert task.status == "needsAction"  # no completion guess
    assert task.completed is None
    assert (task.priority, task.project_name, task.estimated_time_minutes) == ("high", "Home", 15)


def test_gone_task_keeps_its_completed_status_and_timestamp(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "done", "title": "Done", "status": "completed", "completed": "2026-01-01T10:00:00.000Z",
    }, user_id=user.id)

    run_sync(single_list([]))

    task = stored(db, user, "done")
    assert task.deleted is True
    assert task.status == "completed"
    assert task.completed == "2026-01-01T10:00:00.000Z"


def test_tasks_of_a_list_that_disappeared_are_marked_deleted(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "kept", "title": "K", "tasklist_id": "list1"}, user_id=user.id)
    crud.create_or_update_task(db, {"id": "orphan", "title": "O", "tasklist_id": "deletedList"}, user_id=user.id)
    crud.create_or_update_task(db, {"id": "nolist", "title": "N"}, user_id=user.id)

    run_sync(single_list([{"id": "kept", "title": "K", "status": "needsAction"}]))

    assert stored(db, user, "kept").deleted is False
    assert stored(db, user, "orphan").deleted is True
    assert stored(db, user, "nolist").deleted is True


def test_gone_task_comes_back_when_google_returns_it_again(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T", "deleted": True, "priority": "low", "project_name": "P",
        "estimated_time_minutes": 5,
    }, user_id=user.id)

    run_sync(single_list([{"id": "t1", "title": "T", "status": "needsAction"}]))

    task = stored(db, user, "t1")
    assert task.deleted is False
    assert (task.priority, task.project_name, task.estimated_time_minutes) == ("low", "P", 5)


def test_task_moved_to_another_list_is_not_marked_deleted(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "t1", "title": "T", "status": "needsAction", "tasklist_id": "listA", "priority": "high",
    }, user_id=user.id)
    google = FakeGoogle(
        tasklists=[[{"id": "listA", "title": "A"}, {"id": "listB", "title": "B"}]],
        tasks={"listA": [[]], "listB": [[{"id": "t1", "title": "T", "status": "needsAction"}]]},
    )

    run_sync(google)

    task = stored(db, user, "t1")
    assert task.tasklist_id == "listB"
    assert task.deleted is False
    assert task.priority == "high"


def test_tasks_of_other_users_are_never_touched(db, user, run_sync):
    other_id = crud.create_user(db, email="other@example.com", google_tokens={"access_token": "x"}).id
    crud.create_or_update_task(db, {"id": "theirs", "title": "T", "status": "needsAction"}, user_id=other_id)

    run_sync(single_list([]))

    assert crud.get_task(db, "theirs", other_id).deleted in (False, None)


def test_every_local_task_is_checked_not_only_the_first_hundred(db, user, run_sync):
    for i in range(150):
        crud.create_or_update_task(db, {"id": f"old{i}", "title": "T"}, user_id=user.id)

    run_sync(single_list([]))

    assert len(crud.get_user_tasks(db, user.id)) == 0
    assert len(crud.get_user_tasks(db, user.id, include_deleted=True)) == 150


# --- No list (D3) ---

def test_no_task_list_ends_without_error_and_marks_nothing(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "t1", "title": "T", "status": "needsAction"}, user_id=user.id)

    run_sync(FakeGoogle(tasklists=[[]], tasks={}))

    task = stored(db, user, "t1")
    assert task.deleted in (False, None)
    assert task.status == "needsAction"


# --- One transaction per sync (D7) ---

def test_google_failure_on_a_later_page_leaves_the_database_unchanged(db, user, run_sync):
    crud.create_or_update_task(db, {
        "id": "a0", "title": "Before", "status": "needsAction", "tasklist_id": "listA", "priority": "high",
    }, user_id=user.id)
    crud.create_or_update_task(db, {"id": "stale", "title": "Stale", "tasklist_id": "listA"}, user_id=user.id)
    google = FakeGoogle(
        tasklists=[[{"id": "listA", "title": "A"}]],
        tasks={"listA": [
            [{"id": "a0", "title": "After", "status": "completed"}, {"id": "a1", "title": "New"}],
            [{"id": "a2", "title": "Never read"}],
        ]},
        fail_on=("listA", 1),
    )

    with pytest.raises(ValueError):
        run_sync(google)

    assert stored(db, user, "a0").title == "Before"
    assert stored(db, user, "a0").status == "needsAction"
    assert stored(db, user, "a1") is None
    assert stored(db, user, "stale").deleted in (False, None)


def test_database_error_rolls_back_the_whole_sync(db, user, run_sync):
    crud.create_or_update_task(db, {"id": "t1", "title": "Before"}, user_id=user.id)

    with patch.object(db, "commit", side_effect=RuntimeError("disk full")):
        with pytest.raises(ValueError):
            run_sync(single_list([{"id": "t1", "title": "After"}, {"id": "t2", "title": "New"}]))

    assert stored(db, user, "t1").title == "Before"
    assert stored(db, user, "t2") is None


def test_sync_commits_once(db, user, run_sync):
    with patch.object(db, "commit", wraps=db.commit) as commit:
        run_sync(single_list(make_tasks("t", 5)))
    assert commit.call_count == 1


# --- Logs (D9) ---

def test_sync_output_has_no_task_or_list_titles(db, user, run_sync, capsys):
    crud.create_or_update_task(db, {"id": "gone", "title": "Secret gone title"}, user_id=user.id)
    google = FakeGoogle(
        tasklists=[[{"id": "list1", "title": "Secret list title"}]],
        tasks={"list1": [[{"id": "t1", "title": "Secret task title", "notes": "Secret notes"}]]},
    )

    run_sync(google)

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Secret" not in output
    assert "list1" in output  # IDs and counts are printed


def test_sync_error_output_has_no_titles_from_the_sync_itself(db, user, run_sync, capsys):
    google = FakeGoogle(
        tasklists=[[{"id": "list1", "title": "Secret list title"}]],
        tasks={"list1": [[{"id": "t1", "title": "Secret task title"}]]},
        fail_on=("list1", 0),
    )

    with pytest.raises(ValueError):
        run_sync(google)

    assert "Secret" not in capsys.readouterr().out


# --- A repeated page token ---

def test_repeated_page_token_stops_the_sync_and_rolls_back(db, user, run_sync, capsys):
    crud.create_or_update_task(db, {"id": "t1", "title": "Before", "tasklist_id": "list1"}, user_id=user.id)
    pages = {None: {"items": [{"id": "t1", "title": "Secret after"}], "nextPageToken": "same"},
             "same": {"items": [{"id": "t2", "title": "Secret two"}], "nextPageToken": "same"}}
    calls = []

    class LoopingTasks:
        def list(self, **kwargs):
            calls.append(kwargs.get("pageToken"))
            request = MagicMock()
            request.execute.side_effect = lambda: pages[kwargs.get("pageToken")]
            return request

    google = single_list([])
    google.tasks = lambda: LoopingTasks()

    with pytest.raises(ValueError):
        run_sync(google)

    assert calls == [None, "same"]  # the loop ended instead of asking for "same" again
    assert stored(db, user, "t1").title == "Before"
    assert stored(db, user, "t2") is None
    assert "Secret" not in capsys.readouterr().out


# --- Error messages carry no task data (#104) ---

SECRETS = ("Secret title one", "Secret notes one", "Secret title two", "Secret notes two")


def collide_with_another_users_task(db):
    """
    Stores a task of another user under the ID the sync will insert, so the commit
    fails on the primary key and the error text holds the parameters of the insert.
    """
    other = crud.create_user(db, email="other@example.com", google_tokens={"access_token": "valid"})
    crud.create_or_update_task(db, {"id": "dup", "title": "Other user task"}, user_id=other.id)


def colliding_google():
    return single_list([
        {"id": "new1", "title": SECRETS[0], "notes": SECRETS[1]},
        {"id": "dup", "title": SECRETS[2], "notes": SECRETS[3]},
    ])


def test_database_error_output_has_no_task_titles_or_notes(db, user, run_sync, capsys):
    collide_with_another_users_task(db)

    with pytest.raises(ValueError):
        run_sync(colliding_google())

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Error syncing tasks for user" in output
    assert "IntegrityError" in output
    for secret in SECRETS:
        assert secret not in output


def test_raised_error_has_no_task_data_and_no_chained_exception(db, user, run_sync):
    collide_with_another_users_task(db)

    with pytest.raises(ValueError) as raised:
        run_sync(colliding_google())

    error = raised.value
    assert str(error) == "Google Tasks sync failed (IntegrityError)"
    assert error.__suppress_context__ is True
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    for secret in SECRETS:
        assert secret not in str(error)
        assert secret not in rendered


def test_google_http_error_gives_the_type_and_the_status_only(db, user, run_sync, capsys):
    body = b'{"error": {"message": "Secret title one Secret notes one"}}'
    http_error = HttpError(SimpleNamespace(status=503, reason="Secret title two"), body)
    google = single_list([])
    google.tasklists = MagicMock(side_effect=http_error)

    with pytest.raises(ValueError) as raised:
        run_sync(google)

    error = raised.value
    assert str(error) == "Google Tasks sync failed (HttpError, HTTP status 503)"
    assert error.__suppress_context__ is True
    captured = capsys.readouterr()
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    for text in (str(error), rendered, captured.out, captured.err):
        for secret in SECRETS:
            assert secret not in text
    assert "HTTP status 503" in captured.out


def test_database_error_still_rolls_back_the_whole_sync(db, user, run_sync):
    collide_with_another_users_task(db)
    crud.create_or_update_task(db, {"id": "t1", "title": "Before"}, user_id=user.id)
    google = single_list([
        {"id": "t1", "title": "After"},
        {"id": "new1", "title": SECRETS[0]},
        {"id": "dup", "title": SECRETS[2]},
    ])

    with pytest.raises(ValueError):
        run_sync(google)

    assert stored(db, user, "t1").title == "Before"
    assert stored(db, user, "new1") is None
