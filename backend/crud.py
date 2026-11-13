from sqlalchemy.orm import Session
from . import models

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, email: str, google_tokens: dict):
    db_user = models.User(email=email, google_tokens=google_tokens)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_tokens(db: Session, user_id: int, google_tokens: dict):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db_user.google_tokens = google_tokens
        db.commit()
        db.refresh(db_user)
    return db_user

def get_tasks(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Task).filter(models.Task.owner_id == user_id).offset(skip).limit(limit).all()

def get_task(db: Session, task_id: str, user_id: int):
    return db.query(models.Task).filter(models.Task.id == task_id, models.Task.owner_id == user_id).first()

def create_or_update_task(db: Session, task_data: dict, user_id: int):
    db_task = db.query(models.Task).filter(models.Task.id == task_data['id'], models.Task.owner_id == user_id).first()
    
    if db_task:
        for key, value in task_data.items():
            current_value = getattr(db_task, key, None)
            if current_value != value:
                setattr(db_task, key, value)
        db.add(db_task)
    else:
        db_task = models.Task(**task_data, owner_id=user_id)
        db.add(db_task)
        
    db.commit()
    db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: str, user_id: int):
    db_task = db.query(models.Task).filter(models.Task.id == task_id, models.Task.owner_id == user_id).first()
    if db_task:
        db.delete(db_task)
        db.commit()
        return True
    return False
