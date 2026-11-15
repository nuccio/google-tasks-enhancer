import time
import re
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest # Renamed to avoid a name clash
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from . import crud, models
from .database import SessionLocal

load_dotenv() # Load the variables from .env

def get_google_tasks_service(db: Session, user: models.User):
    credentials_data = user.google_tokens
    
    credentials = Credentials(
        token=credentials_data['access_token'],
        refresh_token=credentials_data.get('refresh_token'), # .get() because it may be missing
        client_id=os.getenv("GOOGLE_CLIENT_ID"), # Read from .env
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"), # Read from .env
        token_uri="https://oauth2.googleapis.com/token" # Hardcoded; could come from discovery or .env for consistency
    )
    
    google_auth_request = GoogleAuthRequest()

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(google_auth_request)
            # Store the refreshed tokens in the database
            user.google_tokens = credentials.to_json() # Replace the user's tokens
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"DEBUG: Tokens refreshed for user {user.id}")
        except Exception as e:
            print(f"Error refreshing tokens for user {user.id}: {e}")
            raise # Re-raise to stop the sync if the refresh fails
    
    return build('tasks', 'v1', credentials=credentials)

def extract_hashtags(title: str) -> list[str]:
    return re.findall(r'#(\w+)', title)

def sync_tasks_for_user(user_id: int):
    db: Session = SessionLocal()
    try:
        user = crud.get_user(db, user_id=user_id)
        if not user or not user.google_tokens:
            print(f"User {user_id} not found or no Google tokens.")
            return

        service = get_google_tasks_service(db, user) # Pass db and user

        # TODO: Implement "smart polling" here.
        # For now all tasks are downloaded (to improve with updatedMin)
        results = service.tasklists().list().execute()
        items = results.get('items', [])
        print(f"DEBUG: Found {len(items)} task lists.")

        for tasklist in items:
            print(f"DEBUG: Syncing tasks for list: {tasklist['title']}")
            tasks_results = service.tasks().list(tasklist=tasklist['id'], showCompleted=True).execute()
            tasks = tasks_results.get('items', [])
            print(f"DEBUG: Found {len(tasks)} tasks in this list.")

            for task_data in tasks:
                print(f"DEBUG: Processing task: {task_data.get('title', 'No Title')}")
                # Keep the task list ID for later update operations
                task_data['tasklist_id'] = tasklist['id']
                
                # Extract the hashtags from the title
                task_data['hashtags'] = extract_hashtags(task_data.get('title', ''))

                # Defaults for the custom fields when they are missing
                if 'priority' not in task_data: task_data['priority'] = models.DEFAULT_PRIORITY
                if 'project_name' not in task_data: task_data['project_name'] = None
                if 'estimated_time_minutes' not in task_data: task_data['estimated_time_minutes'] = None

                # Map Google Tasks' 'due' to 'due_date', the name used by the DB model
                if 'due' in task_data:
                    task_data['due_date'] = task_data.pop('due')
                else:
                    task_data['due_date'] = None # Always present, even if None

                crud.create_or_update_task(db, task_data, user_id)
        
        # Mark as completed the local tasks that Google no longer returns
        local_task_ids = {t.id for t in crud.get_tasks(db, user_id)}
        google_task_ids = {t['id'] for t in tasks}
        
        tasks_to_mark_completed_locally = local_task_ids - google_task_ids
        
        if tasks_to_mark_completed_locally:
            print(f"DEBUG: Found {len(tasks_to_mark_completed_locally)} tasks in DB not returned by Google. Marking as completed.")
            for task_id in tasks_to_mark_completed_locally:
                db_task = crud.get_task(db, task_id, user_id)
                if db_task and db_task.status != "completed":
                    db_task.status = "completed"
                    db_task.completed = datetime.now(timezone.utc).isoformat() + 'Z' # ISO 8601 UTC timestamp
                    db.add(db_task)
                    db.commit()
                    db.refresh(db_task)
                    print(f"DEBUG: Task {task_id} marked completed locally.")

        print(f"Synced tasks for user {user.id}")

    except Exception as e:
        # Catch the error and re-raise it with a more specific message
        error_message = f"Google Tasks API error: {e}"
        print(f"Error syncing tasks for user {user.id}: {error_message}")
        raise ValueError(error_message) # Re-raised as ValueError, which the endpoints turn into an HTTP error
    finally:
        db.close()

def update_task_status_on_google(db: Session, user_id: int, task_id: str, tasklist_id: str, new_status: str):
    """
    Updates the status of a task directly through the Google Tasks API.
    new_status must be 'needsAction' or 'completed'
    """
    try:
        user = crud.get_user(db, user_id=user_id)
        if not user or not user.google_tokens:
            raise ValueError("User not found or not authenticated with Google")

        service = get_google_tasks_service(db, user)
        
        # The Google API needs the task object to update it.
        # Fetch the current task so the other fields are not overwritten.
        task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        task['status'] = new_status
        if new_status == 'completed':
            # Sending the timestamp is good practice, even though Google sets it too
            task['completed'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        else:
            # For needsAction null cannot be sent: the keys must be removed
            task.pop('completed', None)
            task.pop('hidden', None) # Completed tasks are sometimes hidden

        # Use patch instead of update: patch sends only the given fields, which is safer.
        updated_task = service.tasks().patch(tasklist=tasklist_id, task=task_id, body=task).execute()
        return updated_task
    except Exception as e:
        error_message = f"Error updating task on Google: {e}"
        print(error_message)
        raise ValueError(error_message)

scheduler = BackgroundScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

def add_user_to_sync(user_id: int, interval_minutes: int = 5, run_immediately: bool = True):
    # Avoid adding the same job twice
    job_id = f"sync_user_{user_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(sync_tasks_for_user, 'interval', minutes=interval_minutes, args=[user_id], id=job_id)
    if run_immediately:
        sync_tasks_for_user(user_id) # Run an immediate sync

def sync_all_existing_users_on_startup():
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).all()
        for user in users:
            add_user_to_sync(user.id) # Add to the scheduler and sync immediately
    except Exception as e:
        print(f"Error syncing all existing users on startup: {e}")
    finally:
        db.close()
