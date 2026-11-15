import pytest
from unittest.mock import patch, MagicMock
from backend import crud

def test_root_serves_frontend(client):
    # Login is handled by the frontend: "/" is public and never redirects.
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200

def test_me_unauthorized(client):
    response = client.get("/auth/me")
    assert response.status_code == 401

def test_get_tasks_unauthorized(client):
    response = client.get("/tasks/")
    assert response.status_code == 401

@patch("backend.scheduler.sync_tasks_for_user")
def test_force_sync_unauthorized(mock_sync, client):
    response = client.post("/tasks/sync")
    assert response.status_code == 401
    mock_sync.assert_not_called()

# To test authorized endpoints without handling real session cookies, the user could
# come from a dependency instead of being read directly from the session.
# Since the current code reads request.session, full integration tests would
# need a more complex setup. For now these basic tests are enough.
