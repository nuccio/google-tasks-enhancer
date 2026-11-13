from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
from fastapi.staticfiles import StaticFiles

from . import models, database, crud, auth, scheduler

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    project_name: Optional[str] = None
    estimated_time_minutes: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "completed",
                "priority": "alta"
            }
        }
    }

# Creazione del database all'avvio
print("DEBUG: Attempting to create database tables...")
models.Base.metadata.create_all(bind=database.engine)
print("DEBUG: Database tables creation attempted.")

app = FastAPI(
    title="Google Tasks Enhancer API",
    description="""
API per estendere le funzionalità di Google Tasks.
Permette la sincronizzazione automatica, l'estrazione di hashtag dai titoli, 
e la gestione di campi personalizzati come priorità e progetti.
""",
    version="0.1.0",
    contact={
        "name": "Google Tasks Enhancer Team",
    },
)

# Aggiungi il middleware per le sessioni (necessario per OAuth)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

# Includi il router di autenticazione
app.include_router(auth.router, prefix="/auth", tags=["Autenticazione"])

@app.on_event("startup")
def startup_event():
    scheduler.start_scheduler()
    scheduler.sync_all_existing_users_on_startup() # Sincronizza tutti gli utenti esistenti all'avvio
    print("Scheduler started and initial sync initiated for existing users.")

@app.get("/tasks/", tags=["Tasks"])
async def get_all_tasks(request: Request, db: Session = Depends(database.get_db)):
    """
    Recupera tutti i task dell'utente loggato dal database locale.
    Include i campi extra come priority, hashtags e project_name.
    """
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_email = request.session['user']['email']
    user = crud.get_user_by_email(db, email=user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in DB")

    tasks = crud.get_tasks(db, user_id=user.id)
    return tasks

@app.post("/tasks/sync", tags=["Tasks"], summary="Forza sincronizzazione")
async def force_sync(request: Request, db: Session = Depends(database.get_db)):
    """
    Avvia immediatamente un ciclo di sincronizzazione con Google Tasks per l'utente loggato.
    Utile se non si vuole aspettare il ciclo automatico dello scheduler.
    """
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_email = request.session['user']['email']
    user = crud.get_user_by_email(db, email=user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in DB")

    try:
        scheduler.sync_tasks_for_user(user.id)
        return {"message": "Sync initiated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.patch("/tasks/{task_id}", tags=["Tasks"], summary="Aggiorna un task")
async def update_task(
    task_id: str, 
    task_update: TaskUpdate, 
    request: Request, 
    db: Session = Depends(database.get_db)
):
    """
    Aggiorna i campi di un task. Se viene modificato lo 'status', la modifica 
    viene inviata anche alle API di Google Tasks.
    """
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_email = request.session['user']['email']
    user = crud.get_user_by_email(db, email=user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in DB")

    db_task = crud.get_task(db, task_id, user.id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Se lo status è cambiato, aggiorna su Google
    google_data = {}
    if task_update.status and task_update.status != db_task.status:
        if not db_task.tasklist_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Tasklist ID missing for this task. Try to sync first."
            )
        try:
            # Riceviamo i dati aggiornati da Google (inclusi i timestamp)
            google_data = scheduler.update_task_status_on_google(
                db, user.id, task_id, db_task.tasklist_id, task_update.status
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Aggiorna localmente: uniamo i dati dell'utente con quelli di Google
    # exclude_unset=True assicura che vengano considerati SOLO i campi inviati nel JSON
    update_data = task_update.model_dump(exclude_unset=True) if hasattr(task_update, 'model_dump') else task_update.dict(exclude_unset=True)

    if google_data:
        # google_data contiene 'status', 'completed', 'updated', 'etag', ecc.
        update_data.update(google_data)

    updated_task = crud.create_or_update_task(db, {"id": task_id, **update_data}, user.id)


    return updated_task

@app.get("/auth/me", tags=["Autenticazione"], summary="Get current user info")
async def get_current_user(request: Request):
    """
    Returns the email of the currently authenticated user.
    """
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"email": request.session['user']['email']}

# Serve static files from the frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    print(f"WARNING: Frontend static files directory not found at {STATIC_DIR}")

@app.get("/{full_path:path}", tags=["Generale"])
async def serve_frontend(request: Request, full_path: str):
    """
    Serve the frontend application.
    """
    html_file_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_file_path):
        with open(html_file_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return {"message": "Frontend not built yet or index.html not found."}

# TODO: Aggiungere logica per aggiungere l'utente allo scheduler dopo il primo login
# Questo richiederà di modificare auth.py per chiamare scheduler.add_user_to_sync
# dopo aver creato o aggiornato l'utente.

# TODO: Aggiungere endpoint per la gestione CRUD dei task personalizzati tramite API
# (es. aggiornare priorità, project_name, estimated_time_minutes)
