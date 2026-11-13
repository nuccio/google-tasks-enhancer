import time
import re
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest # Rinomina per evitare conflitti
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from . import crud, models
from .database import SessionLocal

load_dotenv() # Carica le variabili da .env

def get_google_tasks_service(db: Session, user: models.User):
    credentials_data = user.google_tokens
    
    credentials = Credentials(
        token=credentials_data['access_token'],
        refresh_token=credentials_data.get('refresh_token'), # Usa .get() nel caso sia mancante
        client_id=os.getenv("GOOGLE_CLIENT_ID"), # Ottieni da .env
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"), # Ottieni da .env
        token_uri="https://oauth2.googleapis.com/token" # Hardcode o ottieni da discovery, ma da .env è meglio per consistenza
    )
    
    google_auth_request = GoogleAuthRequest()

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(google_auth_request)
            # Aggiorna i token nel DB dopo il refresh
            user.google_tokens = credentials.to_json() # Aggiorna i token dell'utente
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"DEBUG: Tokens refreshed for user {user.id}")
        except Exception as e:
            print(f"Error refreshing tokens for user {user.id}: {e}")
            raise # Rilancia l'eccezione per fermare la sync se il refresh fallisce
    
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

        service = get_google_tasks_service(db, user) # Passa db e user

        # TODO: Implementare la logica di "smart polling" qui
        # Per ora, scarichiamo tutti i task (da migliorare con updatedMin)
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
                # Aggiungi l'ID della tasklist per le future operazioni di update
                task_data['tasklist_id'] = tasklist['id']
                
                # Estrai gli hashtags dal titolo
                task_data['hashtags'] = extract_hashtags(task_data.get('title', ''))

                # Aggiungi default per i campi personalizzati se non presenti
                if 'priority' not in task_data: task_data['priority'] = "media"
                if 'project_name' not in task_data: task_data['project_name'] = None
                if 'estimated_time_minutes' not in task_data: task_data['estimated_time_minutes'] = None

                # Mappa 'due' da Google Tasks a 'due_date' per consistenza con il modello DB
                if 'due' in task_data:
                    task_data['due_date'] = task_data.pop('due')
                else:
                    task_data['due_date'] = None # Assicurati che sia sempre presente, anche se None

                crud.create_or_update_task(db, task_data, user_id)
        
        # Logica per marcare come completati i task non restituiti da Google
        local_task_ids = {t.id for t in crud.get_tasks(db, user_id)}
        google_task_ids = {t['id'] for t in tasks}
        
        tasks_to_mark_completed_locally = local_task_ids - google_task_ids
        
        if tasks_to_mark_completed_locally:
            print(f"DEBUG: Found {len(tasks_to_mark_completed_locally)} tasks in DB not returned by Google. Marking as completed.")
            for task_id in tasks_to_mark_completed_locally:
                db_task = crud.get_task(db, task_id, user_id)
                if db_task and db_task.status != "completed":
                    db_task.status = "completed"
                    db_task.completed = datetime.now(timezone.utc).isoformat() + 'Z' # Timestamp ISO 8601 UTC
                    db.add(db_task)
                    db.commit()
                    db.refresh(db_task)
                    print(f"DEBUG: Task {task_id} marked completed locally.")

        print(f"Synced tasks for user {user.id}")

    except Exception as e:
        # Cattura l'errore e rilancia con un messaggio più specifico
        error_message = f"Google Tasks API error: {e}"
        print(f"Error syncing tasks for user {user.id}: {error_message}")
        raise ValueError(error_message) # Rilancia come ValueError per FastAPI
    finally:
        db.close()

def update_task_status_on_google(db: Session, user_id: int, task_id: str, tasklist_id: str, new_status: str):
    """
    Aggiorna lo stato di un task direttamente sulle API di Google Tasks.
    new_status deve essere 'needsAction' o 'completed'
    """
    try:
        user = crud.get_user(db, user_id=user_id)
        if not user or not user.google_tokens:
            raise ValueError("User not found or not authenticated with Google")

        service = get_google_tasks_service(db, user)
        
        # Google API richiede l'oggetto task per fare l'update. 
        # Recuperiamo il task attuale per non sovrascrivere altri campi.
        task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        task['status'] = new_status
        if new_status == 'completed':
            # E' buona norma mandare il timestamp, anche se Google lo imposta da solo
            task['completed'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        else:
            # Se è needsAction, non possiamo mandare null. Dobbiamo rimuovere le chiavi!
            task.pop('completed', None)
            task.pop('hidden', None) # I task completati a volte vengono nascosti

        # Usa patch invece di update. Patch invia solo i campi forniti, molto più sicuro.
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
    # Evita di aggiungere lo stesso job più volte
    job_id = f"sync_user_{user_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(sync_tasks_for_user, 'interval', minutes=interval_minutes, args=[user_id], id=job_id)
    if run_immediately:
        sync_tasks_for_user(user_id) # Esegui una sincronizzazione immediata

def sync_all_existing_users_on_startup():
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).all()
        for user in users:
            add_user_to_sync(user.id) # Aggiungi allo scheduler e sincronizza immediatamente
    except Exception as e:
        print(f"Error syncing all existing users on startup: {e}")
    finally:
        db.close()
