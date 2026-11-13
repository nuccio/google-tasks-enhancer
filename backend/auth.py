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
    Inizia il flusso di autenticazione OAuth2 con Google.
    Reindirizza l'utente alla pagina di login di Google.
    """
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/google', name='auth_callback')
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint di callback per Google OAuth2.
    Riceve il token, crea o aggiorna l'utente nel database e avvia la sincronizzazione dei task.
    """
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    # Salva o aggiorna l'utente nel DB
    user = crud.get_user_by_email(db, email=user_info['email'])
    if not user:
        user = crud.create_user(db, email=user_info['email'], google_tokens=token)
        # Assicuriamoci che anche i nuovi utenti siano aggiunti allo scheduler
        scheduler.add_user_to_sync(user.id)
    else:
        crud.update_user_tokens(db, user_id=user.id, google_tokens=token)
        scheduler.add_user_to_sync(user.id) # Ri-aggiungi/aggiorna lo scheduler

    request.session['user'] = user_info
    return RedirectResponse(url='/') # Reindirizza alla UI