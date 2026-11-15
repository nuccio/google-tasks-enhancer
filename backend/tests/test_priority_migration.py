"""English priority values: data migration, defaults and API validation."""
import base64
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from starlette.middleware.sessions import SessionMiddleware

from backend import crud, models

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "alembic"
PRIORITY_REVISION = "c3a91e7d5b24"
PREVIOUS_HEAD = "fb815bf08509"

# One row per case: id -> (value before the upgrade, value after it)
CASES = {
    "t_media": ("media", "medium"),
    "t_alta": ("alta", "high"),
    "t_bassa": ("bassa", "low"),
    "t_upper": ("Alta", "high"),
    "t_spaces": (" media ", "medium"),
    "t_low": ("low", "low"),
    "t_medium": ("medium", "medium"),
    "t_high": ("high", "high"),
    "t_empty": ("", ""),
    "t_null": (None, None),
    "t_unexpected": ("urgent", "urgent"),
}


def _script() -> ScriptDirectory:
    return ScriptDirectory(str(SCRIPT_DIR))


def _run(connection, direction: str) -> None:
    """Run the revision through Alembic's API, without alembic/env.py."""
    module = _script().get_revision(PRIORITY_REVISION).module
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _priorities(connection) -> dict:
    rows = connection.execute(sa.text("SELECT id, priority FROM tasks")).fetchall()
    return {row[0]: row[1] for row in rows}


@pytest.fixture
def throwaway_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration-test.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE tasks (id VARCHAR PRIMARY KEY, priority VARCHAR)"))
        for task_id, (before, _) in CASES.items():
            connection.execute(
                sa.text("INSERT INTO tasks (id, priority) VALUES (:id, :priority)"),
                {"id": task_id, "priority": before},
            )
    yield engine
    engine.dispose()


def test_upgrade_maps_italian_values_and_leaves_the_rest(throwaway_engine):
    with throwaway_engine.begin() as connection:
        _run(connection, "upgrade")
    with throwaway_engine.connect() as connection:
        assert _priorities(connection) == {k: after for k, (_, after) in CASES.items()}


def test_downgrade_applies_the_inverse_mapping(throwaway_engine):
    with throwaway_engine.begin() as connection:
        _run(connection, "upgrade")
        _run(connection, "downgrade")
    with throwaway_engine.connect() as connection:
        assert _priorities(connection) == {
            "t_media": "media",
            "t_alta": "alta",
            "t_bassa": "bassa",
            "t_upper": "alta",
            "t_spaces": "media",
            # Rows that were already English also become Italian (see the docstring)
            "t_low": "bassa",
            "t_medium": "media",
            "t_high": "alta",
            "t_empty": "",
            "t_null": None,
            "t_unexpected": "urgent",
        }


def test_revisions_form_one_chain_with_a_single_head():
    script = _script()
    assert script.get_heads() == [PRIORITY_REVISION]
    assert script.get_bases() == ["123348add1f3"]
    revisions = list(script.walk_revisions())
    for revision in revisions:
        assert len(revision.nextrev) <= 1, f"{revision.revision} has several children"
        assert not revision.is_merge_point
    assert script.get_revision(PRIORITY_REVISION).down_revision == PREVIOUS_HEAD


def test_column_default_and_sync_default_are_the_same_constant():
    assert models.DEFAULT_PRIORITY == "medium"
    assert models.DEFAULT_PRIORITY in models.PRIORITY_VALUES
    assert models.Task.__table__.c.priority.default.arg == models.DEFAULT_PRIORITY


def test_new_task_without_priority_gets_the_default(db):
    user = crud.create_user(db, email="default@example.com", google_tokens={"access_token": "abc"})
    task = crud.create_or_update_task(db, {"id": "t1", "title": "T1"}, user_id=user.id)
    assert task.priority == "medium"


def _session_cookie(app, session: dict) -> str:
    """Sign a session cookie with the key of the app's own SessionMiddleware."""
    layer = app.middleware_stack
    while layer is not None and not isinstance(layer, SessionMiddleware):
        layer = getattr(layer, "app", None)
    assert layer is not None, "SessionMiddleware not found in the middleware stack"
    payload = base64.b64encode(json.dumps(session).encode("utf-8"))
    return layer.signer.sign(payload).decode("utf-8")


@pytest.fixture
def logged_in_client(client, db):
    user = crud.create_user(db, email="patch@example.com", google_tokens={"access_token": "abc"})
    crud.create_or_update_task(db, {"id": "task1", "title": "T", "priority": "medium"}, user_id=user.id)
    client.cookies.set("session", _session_cookie(client.app, {"user": {"email": "patch@example.com"}}))
    return client


@pytest.mark.parametrize("value", ["low", "medium", "high", None])
def test_patch_accepts_english_priorities_and_null(logged_in_client, value):
    response = logged_in_client.patch("/tasks/task1", json={"priority": value})
    assert response.status_code == 200
    assert response.json()["priority"] == value


@pytest.mark.parametrize("value", ["alta", "media", "bassa", "urgent", "", "High", 3])
def test_patch_rejects_other_values_with_an_english_message(logged_in_client, value):
    response = logged_in_client.patch("/tasks/task1", json={"priority": value})
    assert response.status_code == 422
    if isinstance(value, str):
        assert "low, medium, high" in response.text


def test_patch_without_priority_leaves_it_unchanged(logged_in_client):
    response = logged_in_client.patch("/tasks/task1", json={"project_name": "home"})
    assert response.status_code == 200
    assert response.json()["priority"] == "medium"
