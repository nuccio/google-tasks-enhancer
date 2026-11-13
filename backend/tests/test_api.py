import pytest
from unittest.mock import patch, MagicMock
from backend import crud

def test_root_redirect_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert "/auth/login/google" in response.headers["location"]

def test_get_tasks_unauthorized(client):
    response = client.get("/tasks/")
    assert response.status_code == 401

@patch("backend.scheduler.sync_tasks_for_user")
def test_force_sync_unauthorized(mock_sync, client):
    response = client.post("/tasks/sync")
    assert response.status_code == 401
    mock_sync.assert_not_called()

# Per testare endpoint autorizzati senza dover gestire i cookie di sessione reali,
# potremmo usare una dipendenza per l'utente invece di leggere direttamente dalla sessione.
# Ma dato che il codice attuale legge da request.session, i test di integrazione completi
# richiederebbero un setup più complesso. Per ora ci fermiamo a questi test di base.
