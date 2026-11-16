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

# Who owns which column of a task row (design #97, section 3).
# Google-owned columns, written on every sync: the model column mapped to the field name
# in Google's task resource. This is the only way Google data reaches a task row.
GOOGLE_FIELDS = {
    "kind": "kind",
    "etag": "etag",
    "title": "title",
    "updated": "updated",
    "selfLink": "selfLink",
    "parent": "parent",
    "position": "position",
    "notes": "notes",
    "status": "status",
    "due_date": "due",  # Google's 'due' is stored as 'due_date'
    "completed": "completed",
    "deleted": "deleted",
    "hidden": "hidden",
    "webViewLink": "webViewLink",
    "assignmentInfo": "assignmentInfo",
    "links": "links",
}
# Google leaves optional fields out of its reply; for these a missing field means False
GOOGLE_BOOLEAN_FIELDS = ("deleted", "hidden")
# Columns set by the sync itself: the list the task was found in
SYNC_FIELDS = ("tasklist_id",)
# Columns derived from another column on every sync
DERIVED_FIELDS = ("hashtags",)
# Columns owned by the user: written only when the sync creates the task
CUSTOM_FIELDS = ("priority", "project_name", "estimated_time_minutes")

TASKS_PAGE_SIZE = 100  # Maximum page size of tasks.list
TASKLISTS_PAGE_SIZE = 1000  # Maximum page size of tasklists.list

def google_task_values(google_task: dict) -> dict:
    """
    The values of the Google-owned columns for a task as Google returned it.
    A field Google left out becomes None ('deleted' and 'hidden': False); fields
    the model does not know are ignored.
    """
    values = {}
    for column, google_key in GOOGLE_FIELDS.items():
        value = google_task.get(google_key)
        if column in GOOGLE_BOOLEAN_FIELDS:
            value = bool(value)
        values[column] = value
    return values

def apply_google_task(db: Session, user_id: int, tasklist_id: str, google_task: dict,
                      existing_tasks: dict):
    """
    Applies one task as Google returned it to the local rows, without committing.
    existing_tasks maps the task ID to the stored row of the user and is kept up to date.
    Returns the row, or None when nothing was stored (the task has no ID, or it arrived
    already deleted and has no local row).
    """
    task_id = google_task.get('id')
    if not task_id:
        return None

    values = google_task_values(google_task)
    values['tasklist_id'] = tasklist_id
    values['hashtags'] = extract_hashtags(values['title'] or '')

    db_task = existing_tasks.get(task_id)
    if db_task is None:
        if values['deleted']:
            return None
        # The custom fields get their defaults only when the task is created
        db_task = models.Task(
            id=task_id,
            owner_id=user_id,
            priority=models.DEFAULT_PRIORITY,
            project_name=None,
            estimated_time_minutes=None,
            **values,
        )
        existing_tasks[task_id] = db_task
    else:
        for column, value in values.items():
            setattr(db_task, column, value)
    db.add(db_task)
    return db_task

def _list_all_pages(request_page):
    """Yields the items of every page of a Google list call; request_page(page_token) builds the request."""
    page_token = None
    seen_tokens = set()
    while True:
        response = request_page(page_token).execute()
        yield from response.get('items', [])
        page_token = response.get('nextPageToken')
        if not page_token:
            return
        if page_token in seen_tokens:
            # Google would send the same page forever: stop, the sync is rolled back
            raise RuntimeError("Google returned the same page token twice")
        seen_tokens.add(page_token)

def sync_tasks_for_user(user_id: int):
    db: Session = SessionLocal()
    try:
        user = crud.get_user(db, user_id=user_id)
        if not user or not user.google_tokens:
            print(f"User {user_id} not found or no Google tokens.")
            return

        service = get_google_tasks_service(db, user) # Pass db and user

        # TODO: Implement "smart polling" here (updatedMin, issue #89).
        # For now every task is downloaded on every sync.
        tasklists = list(_list_all_pages(
            lambda token: service.tasklists().list(maxResults=TASKLISTS_PAGE_SIZE, pageToken=token)
        ))
        print(f"DEBUG: Found {len(tasklists)} task lists for user {user_id}.")
        if not tasklists:
            # Most likely an anomaly: change nothing rather than hide every task of the user
            print(f"DEBUG: No task lists for user {user_id}, nothing synced.")
            return

        # Every row of the user, deleted ones included, with no row cap
        existing_tasks = {t.id: t for t in crud.get_user_tasks(db, user_id, include_deleted=True)}
        returned_ids = set()

        for tasklist in tasklists:
            tasklist_id = tasklist['id']
            count = 0
            for google_task in _list_all_pages(
                lambda token, tasklist_id=tasklist_id: service.tasks().list(
                    tasklist=tasklist_id,
                    maxResults=TASKS_PAGE_SIZE,
                    showCompleted=True,
                    showHidden=True,
                    showDeleted=True,
                    pageToken=token,
                )
            ):
                count += 1
                if google_task.get('id'):
                    returned_ids.add(google_task['id'])
                apply_google_task(db, user_id, tasklist_id, google_task, existing_tasks)
            print(f"DEBUG: List {tasklist_id}: {count} tasks returned.")

        # A task that no list returned is gone on Google: mark it deleted and keep the rest.
        # This runs only after every list was read completely.
        gone = [t for task_id, t in existing_tasks.items() if task_id not in returned_ids and not t.deleted]
        for db_task in gone:
            db_task.deleted = True
            db.add(db_task)
        if gone:
            print(f"DEBUG: {len(gone)} stored tasks not returned by Google, marked deleted.")

        db.commit() # One transaction per sync: all or nothing
        print(f"Synced tasks for user {user_id}")

    except Exception as e:
        db.rollback()
        # Catch the error and re-raise it with a more specific message
        error_message = f"Google Tasks API error: {e}"
        print(f"Error syncing tasks for user {user_id}: {error_message}")
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
