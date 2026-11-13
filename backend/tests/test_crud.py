from backend import crud, models

def test_create_user(db):
    user = crud.create_user(db, email="test@example.com", google_tokens={"access_token": "abc"})
    assert user.email == "test@example.com"
    assert user.id is not None

def test_get_user_by_email(db):
    crud.create_user(db, email="test@example.com", google_tokens={"access_token": "abc"})
    user = crud.get_user_by_email(db, email="test@example.com")
    assert user is not None
    assert user.email == "test@example.com"

def test_create_or_update_task(db):
    user = crud.create_user(db, email="test@example.com", google_tokens={"access_token": "abc"})
    task_data = {
        "id": "task123",
        "title": "Test Task",
        "status": "needsAction",
        "priority": "alta"
    }
    task = crud.create_or_update_task(db, task_data, user_id=user.id)
    assert task.id == "task123"
    assert task.title == "Test Task"
    assert task.owner_id == user.id

    # Update
    task_data["title"] = "Updated Task"
    updated_task = crud.create_or_update_task(db, task_data, user_id=user.id)
    assert updated_task.title == "Updated Task"
    assert updated_task.id == "task123"

def test_get_tasks(db):
    user = crud.create_user(db, email="test@example.com", google_tokens={"access_token": "abc"})
    crud.create_or_update_task(db, {"id": "t1", "title": "T1"}, user_id=user.id)
    crud.create_or_update_task(db, {"id": "t2", "title": "T2"}, user_id=user.id)
    
    tasks = crud.get_tasks(db, user_id=user.id)
    assert len(tasks) == 2

def test_delete_task(db):
    user = crud.create_user(db, email="test@example.com", google_tokens={"access_token": "abc"})
    crud.create_or_update_task(db, {"id": "t1", "title": "T1"}, user_id=user.id)
    
    success = crud.delete_task(db, "t1", user_id=user.id)
    assert success is True
    assert len(crud.get_tasks(db, user_id=user.id)) == 0
