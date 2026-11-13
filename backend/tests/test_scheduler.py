import pytest
from unittest.mock import MagicMock, patch
from backend import scheduler, models, crud

def test_extract_hashtags():
    assert scheduler.extract_hashtags("Comprare latte #casa #spesa") == ["casa", "spesa"]
    assert scheduler.extract_hashtags("Nessun hashtag") == []
    assert scheduler.extract_hashtags("#inizio hashtag") == ["inizio"]

@patch("backend.scheduler.get_google_tasks_service")
@patch("backend.scheduler.SessionLocal")
def test_sync_tasks_for_user(mock_session_local, mock_get_service, db):
    # Setup mock DB session
    mock_session_local.return_value = db
    
    # Setup user
    user = crud.create_user(db, email="sync@example.com", google_tokens={"access_token": "valid"})
    
    # Setup Mock Google Service
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    # Mock tasklists().list().execute()
    mock_service.tasklists().list().execute.return_value = {
        "items": [{"id": "list1", "title": "My List"}]
    }
    
    # Mock tasks().list().execute() - Stato di partenza su Google
    mock_service.tasks().list().execute.return_value = {
        "items": [
            {
                "id": "gtask1",
                "title": "Task from Google #work",
                "status": "needsAction"
            }
        ]
    }
    
    # Esegui sync
    scheduler.sync_tasks_for_user(user.id)
    
    # Verifica che il task sia stato creato localmente
    tasks = crud.get_tasks(db, user_id=user.id)
    assert len(tasks) == 1
    assert tasks[0].id == "gtask1"
    assert tasks[0].hashtags == ["work"]

@patch("backend.scheduler.get_google_tasks_service")
@patch("backend.scheduler.SessionLocal")
def test_sync_tasks_smart_completion(mock_session_local, mock_get_service, db):
    # Setup mock DB session
    mock_session_local.return_value = db
    
    # Setup user
    user = crud.create_user(db, email="sync@example.com", google_tokens={"access_token": "valid"})
    
    # Stato di partenza locale: un task che non esiste più su Google
    crud.create_or_update_task(db, {"id": "old_task", "title": "Old Task", "status": "needsAction"}, user_id=user.id)
    
    # Setup Mock Google Service
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    
    # Mock Google Tasks: restituisce una lista vuota di task
    mock_service.tasklists().list().execute.return_value = {"items": [{"id": "list1", "title": "My List"}]}
    mock_service.tasks().list().execute.return_value = {"items": []}
    
    # Esegui sync
    scheduler.sync_tasks_for_user(user.id)
    
    # Verifica la logica smart: il task locale deve essere marcato come "completed"
    db_task = crud.get_task(db, "old_task", user.id)
    assert db_task.status == "completed"
    assert db_task.completed is not None
