from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from . import crud, models, scheduler
from .database import get_db

load_dotenv()

router = APIRouter()

oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/tasks'
    },
)

@router.get('/login/google', name='login_google')
async def login(request: Request):
    """
    Starts the OAuth2 flow with Google.
    Redirects the user to the Google login page.
    """
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/google', name='auth_callback')
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """
    Callback endpoint for Google OAuth2.
    Receives the token, creates or updates the user in the database and starts the task sync.
    """
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    # Create the user or update their tokens in the database
    user = crud.get_user_by_email(db, email=user_info['email'])
    if not user:
        user = crud.create_user(db, email=user_info['email'], google_tokens=token)
        # New users are added to the scheduler too
        scheduler.add_user_to_sync(user.id)
    else:
        crud.update_user_tokens(db, user_id=user.id, google_tokens=token)
        scheduler.add_user_to_sync(user.id) # Re-add the job to the scheduler

    request.session['user'] = user_info
    return RedirectResponse(url='/') # Redirect to the UI