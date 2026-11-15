from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
import os
from fastapi.staticfiles import StaticFiles

from . import models, database, crud, auth, scheduler, devui

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    project_name: Optional[str] = None
    estimated_time_minutes: Optional[int] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in models.PRIORITY_VALUES:
            allowed = ", ".join(models.PRIORITY_VALUES)
            raise ValueError(f"priority must be one of: {allowed}, or null")
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "completed",
                "priority": "high"
            }
        }
    }

# Create the database tables at startup
print("DEBUG: Attempting to create database tables...")
models.Base.metadata.create_all(bind=database.engine)
print("DEBUG: Database tables creation attempted.")

app = FastAPI(
    title="Google Tasks Enhancer API",
    description="""
API that extends Google Tasks.
It syncs tasks automatically, extracts hashtags from titles,
and manages custom fields such as priority and project.
""",
    version="0.1.0",
    contact={
        "name": "Google Tasks Enhancer Team",
    },
)

# Session middleware (required by OAuth)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

# Authentication router
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Read-only dev UI API: always registered, answers 404 unless DEV_UI_ENABLED is on
app.include_router(devui.router)

@app.on_event("startup")
def startup_event():
    scheduler.start_scheduler()
    scheduler.sync_all_existing_users_on_startup() # Sync all existing users at startup
    print("Scheduler started and initial sync initiated for existing users.")

@app.get("/tasks/", tags=["Tasks"])
async def get_all_tasks(request: Request, db: Session = Depends(database.get_db)):
    """
    Returns all tasks of the logged-in user from the local database.
    Includes the custom fields such as priority, hashtags and project_name.
    """
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_email = request.session['user']['email']
    user = crud.get_user_by_email(db, email=user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in DB")

    tasks = crud.get_tasks(db, user_id=user.id)
    return tasks

@app.post("/tasks/sync", tags=["Tasks"], summary="Force a sync")
async def force_sync(request: Request, db: Session = Depends(database.get_db)):
    """
    Immediately starts a sync with Google Tasks for the logged-in user.
    Useful to avoid waiting for the next automatic run of the scheduler.
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

@app.patch("/tasks/{task_id}", tags=["Tasks"], summary="Update a task")
async def update_task(
    task_id: str, 
    task_update: TaskUpdate, 
    request: Request, 
    db: Session = Depends(database.get_db)
):
    """
    Updates the fields of a task. If 'status' changes, the change is also
    sent to the Google Tasks API.
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

    # If the status changed, update it on Google
    google_data = {}
    if task_update.status and task_update.status != db_task.status:
        if not db_task.tasklist_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Tasklist ID missing for this task. Try to sync first."
            )
        try:
            # Google returns the updated task, including its timestamps
            google_data = scheduler.update_task_status_on_google(
                db, user.id, task_id, db_task.tasklist_id, task_update.status
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Update locally: merge the user's changes with the data returned by Google.
    # exclude_unset=True keeps ONLY the fields sent in the JSON body
    update_data = task_update.model_dump(exclude_unset=True) if hasattr(task_update, 'model_dump') else task_update.dict(exclude_unset=True)

    if google_data:
        # google_data contains 'status', 'completed', 'updated', 'etag', etc.
        update_data.update(google_data)

    updated_task = crud.create_or_update_task(db, {"id": task_id, **update_data}, user.id)


    return updated_task

@app.get("/auth/me", tags=["Authentication"], summary="Get current user info")
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

@app.get("/dev", include_in_schema=False, dependencies=[Depends(devui.require_dev_access)])
@app.get("/dev/", include_in_schema=False, dependencies=[Depends(devui.require_dev_access)])
async def serve_dev_ui():
    """
    Serve the read-only dev UI page, behind the same guard as /dev/api.
    """
    dev_file_path = os.path.join(STATIC_DIR, "dev.html")
    if not os.path.exists(dev_file_path):
        return PlainTextResponse(
            "Dev UI page not built: run `npm run build` in frontend/.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    with open(dev_file_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/{full_path:path}", tags=["General"])
async def serve_frontend(request: Request, full_path: str):
    """
    Serve the frontend application.
    """
    if full_path == "dev/api" or full_path.startswith("dev/api/"):
        # Unknown dev API paths must not fall back to the app's index.html
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    html_file_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_file_path):
        with open(html_file_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return {"message": "Frontend not built yet or index.html not found."}

# TODO: Add the user to the scheduler after the first login.
# This needs auth.py to call scheduler.add_user_to_sync
# after creating or updating the user.

# TODO: Add endpoints to manage the custom task fields through the API
# (for example priority, project_name, estimated_time_minutes)
