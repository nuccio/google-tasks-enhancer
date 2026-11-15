# Google Tasks Enhancer Backend

Questo è il backend di un'applicazione progettata per estendere e gestire le funzionalità di Google Tasks. Permette agli utenti di sincronizzare le proprie attività da Google Tasks, arricchirle con campi personalizzati (come priorità, nome progetto, hashtag e tempo stimato), e mantenerle aggiornate in un database locale. L'applicazione espone un'API REST per l'interazione e include uno scheduler per la sincronizzazione automatica.

## Caratteristiche

*   **Sincronizzazione Bidirezionale (Parziale):** Sincronizza task da Google Tasks al database locale.
*   **Campi Personalizzati:** Aggiunge `priority`, `project_name`, `hashtags` (dedotti dal titolo) e `estimated_time_minutes` ai task.
*   **Autenticazione Google OAuth 2.0:** Supporta il login con account Google per più utenti (Web Application Flow).
*   **Database SQLite:** Utilizza SQLite per la persistenza dei dati, facile da configurare e ideale per lo sviluppo.
*   **API REST:** Espone endpoint per la gestione dei task.
*   **Sincronizzazione Automatica:** Esegue la sincronizzazione di tutti gli utenti registrati all'avvio e poi ogni 5 minuti.

### Logica di Sincronizzazione Dati

Il backend implementa una logica di sincronizzazione "smart" per mantenere il database locale aggiornato con Google Tasks:
1.  **Recupero Completo:** Quando un utente si autentica o all'avvio dello scheduler, l'applicazione recupera **tutti i task** (inclusi quelli completati) dalla Google Tasks API per l'utente.
2.  **Aggiornamento Incrementale:** Ogni task ricevuto dall'API viene confrontato con la versione presente nel database locale. Se il task esiste già, i suoi campi vengono aggiornati. Se è un nuovo task, viene aggiunto.

#### Motivazione per la Gestione dei Task Completati

Abbiamo osservato che, in alcune circostanze, la Google Tasks API, nonostante la richiesta esplicita di includere i task completati (`showCompleted=True`), **non restituisce sempre i task che sono stati marcati come "completati"** dall'interfaccia utente di Google Tasks. Questo crea una discrepanza tra lo stato visibile all'utente e i dati ottenibili tramite API.

Per garantire la coerenza dei dati nel nostro database locale, abbiamo adottato la seguente strategia:
Se un task è presente nel nostro database locale ma **non viene restituito** dalla Google Tasks API durante la sincronizzazione, l'applicazione assume che questo task sia stato completato dall'utente. Di conseguenza, il task viene **automaticamente aggiornato allo stato "completed"** nel database locale, con un timestamp di completamento. Questa logica ci permette di riflettere correttamente lo stato dei task anche in presenza di comportamenti inattesi o filtraggi impliciti da parte dell'API di Google.

## Architettura

Il backend è costruito con **FastAPI** (Python), utilizzando **SQLAlchemy** come ORM e **APScheduler** per i job in background.

Componenti principali:
*   `main.py`: Entrypoint dell'applicazione FastAPI e definizione degli endpoint principali.
*   `auth.py`: Gestione del flusso di autenticazione Google OAuth 2.0.
*   `database.py`: Configurazione della connessione al database SQLite.
*   `models.py`: Definizione dei modelli di database per `User` e `Task`.
*   `crud.py`: Operazioni CRUD (Create, Read, Update, Delete) per i dati del database.
*   `scheduler.py`: Logica per la sincronizzazione dei task in background con Google Tasks.
*   `devui.py`: read-only dev API under `/dev/api` for the local data viewer, off by default (see [Local data viewer](#local-data-viewer-development-only)).

## Setup e Installazione

Per avviare il backend in locale, segui questi passaggi:

### 1. Clona il Repository (se non l'hai già fatto)

```bash
git clone <URL_DEL_TUO_REPOSITORY>
cd google-tasks-enhancer-backend # O il nome della tua directory clonata
```

### 2. Configura le Credenziali Google Cloud

1.  **Google Cloud Console:** Vai su [https://console.cloud.google.com/](https://console.cloud.google.com/).
2.  **Seleziona/Crea Progetto:** Assicurati di essere nel progetto corretto.
3.  **Abilita API:** Vai su `API e servizi > Libreria` e abilita **"Google Tasks API"**.
4.  **Crea Credenziali OAuth 2.0:**
    *   Vai su `API e servizi > Credenziali`.
    *   Clicca `Crea credenziali > ID client OAuth`.
    *   **Tipo di applicazione:** `Applicazione Web`.
    *   **Nome:** `Google Tasks Enhancer Web App` (o simile).
    *   **URI di reindirizzamento autorizzati:** Aggiungi `http://localhost:8000/auth/google`.
    *   Copia **Client ID** e **Client secret**: ti serviranno nel passo successivo. L'applicazione non legge il file JSON scaricabile dalla console, quindi non serve salvarlo nel progetto.

### 3. Configura le Variabili d'Ambiente

Copia `backend/env.example` in `backend/.env` e sostituisci i placeholder con i tuoi valori:

```bash
cp backend/env.example backend/.env
```

```dotenv
GOOGLE_CLIENT_ID=IL_TUO_CLIENT_ID_DA_CREDENTIALS.JSON
GOOGLE_CLIENT_SECRET=LA_TUA_CHIAVE_SECRETA_CLIENT_DA_CREDENTIALS.JSON
SECRET_KEY=UNA_LUNGA_E_CASUALE_STRINGA_SECRETA_PER_LE_SESSIONI_FASTAPI
```
*Assicurati che `SECRET_KEY` sia una stringa lunga e casuale, ad esempio generata con `python3 -c "import secrets; print(secrets.token_hex(32))"`.*

> **Sicurezza:** `backend/.env` e qualsiasi file `client_secret*.json` / `credentials.json` sono esclusi da git tramite `.gitignore`. Non committare mai credenziali reali.

### 4. Installazione delle Dipendenze

Serve Python 3.11 o superiore. Dalla radice del repository:

```bash
python3 -m pip install -r backend/requirements.txt
```

Per il frontend (Node.js) serve solo se vuoi modificarlo o ricompilarlo:

```bash
cd frontend && npm ci && npm run build
```

### 5. Avvio del Server

Dalla radice del repository (le variabili vengono lette da `backend/.env`):

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level debug
```
Per fermare il server, premi `Ctrl+C`.

## Running the checks

```bash
python3 -m pytest backend/tests     # from the repository root; needs backend requirements + pytest installed
cd frontend && npm run build        # type-check + build
cd frontend && npm run lint
```

CI runs these three checks, and all of them are required checks.

## Local data viewer (development only)

A read-only page that shows what the local database holds: overview counts, the users, the tasks with filters and sorting, and every field of a single task. It edits nothing, starts no sync, calls no Google API and stores nothing: the filters live in the page URL. Google token values are never shown; the users list only says whether a user has tokens.

> **Warning: keep it local.** With the flag on, anyone who reaches the API from the same machine can read the titles, notes and email addresses of every user, without logging in. Keep `DEV_UI_ENABLED` off on any machine that other people can reach, and while it is on do not combine it with:
>
> - a reverse proxy in front of the API;
> - an SSH tunnel, ngrok or any other tunnel to the API or to Vite;
> - `npm run dev -- --host` (Vite listening on the network);
> - uvicorn's `--no-proxy-headers`;
> - a custom `--forwarded-allow-ips` or `FORWARDED_ALLOW_IPS`.
>
> The start command above uses `--host 0.0.0.0`. The viewer refuses clients that are not on the same machine, but while the flag is on, `--host 127.0.0.1` is the safer choice.

### Enable and open it

1. Set the flag in `backend/.env` (it is `false` in `backend/env.example`; `true`, `1` and `yes` turn it on). Restart the API after changing it: `backend/.env` is read once at startup.

   ```dotenv
   DEV_UI_ENABLED=true
   ```

2. Build the frontend, then start the API from the repository root:

   ```bash
   cd frontend && npm run build && cd ..
   ```

   ```bash
   python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

3. Open `http://localhost:8000/dev`.

While working on the page itself, run `npm run dev` in `frontend/` with the API running, then open `http://localhost:5173/static/dev.html`. Vite proxies `/dev/api` to `http://localhost:8000`.

### Endpoints

All of them are `GET` requests under `/dev/api`:

| Endpoint | Returns |
| --- | --- |
| `/dev/api/overview` | Counts: users, tasks, deleted, hidden, tasks without list or due date, last update, and counts by status, priority, project and hashtag (top 20). |
| `/dev/api/users` | Every user with id, email, number of tasks and whether Google tokens are stored. |
| `/dev/api/tasks` | `{total, items}`. Filters: `user_id`, `status`, `priority`, `project`, `hashtag`, `q` (text in title or notes), `include_deleted` (also shows deleted and hidden tasks). `sort` is one of `title`, `updated` (default), `due_date`, `priority`, `project_name`, `status`; `order` is `asc` or `desc` (default). `limit` goes from 1 to 500 (default 50), `offset` from 0. |
| `/dev/api/tasks/{id}` | Every field of one task; 404 if it does not exist. |
| `/dev/api/status` | Alembic revision of the database, whether the scheduler is running, and its jobs with their next run time. |

### Responses

- Flag off: `404` on `/dev` and on every `/dev/api/*` path.
- Flag on, but the client is not on the same machine, or the `Host` header is not `localhost`, `127.0.0.1` or `[::1]` (with any port): `403`.
- `/dev` answers `404` with a short message if the page has not been built yet (`npm run build` in `frontend/`).
- Invalid query parameters: `422`.

### Logs

uvicorn's access log records every request URL, so the filter and search values typed in the viewer appear in the terminal. Add `--no-access-log` to the uvicorn command to turn the access log off.

## Utilizzo

### Autenticazione

1.  Apri il tuo browser (preferibilmente in incognito) e vai a `http://localhost:8000/`.
2.  Verrai reindirizzato alla pagina di login di Google. Effettua l'accesso con l'account Google per cui desideri sincronizzare i task (assicurati che sia un utente di test configurato nella Google Cloud Console).
3.  Dopo l'autenticazione, verrai reindirizzato alla pagina `/` del backend.

### Endpoint API

*   **`GET /`**: Home page dell'API (richiede autenticazione).
*   **`GET /auth/login/google`**: Inizia il flusso di autenticazione Google OAuth 2.0.
*   **`GET /auth/google`**: Callback URL per l'autenticazione Google.
*   **`GET /tasks/`**: Recupera tutti i task sincronizzati per l'utente autenticato.
*   **`POST /tasks/sync`**: Forza una sincronizzazione manuale dei task per l'utente autenticato.
*   **`GET /dev`** and **`GET /dev/api/*`**: local read-only data viewer, off by default and for development only (see [Local data viewer](#local-data-viewer-development-only)).

Puoi esplorare e testare gli endpoint tramite la documentazione interattiva di FastAPI all'indirizzo `http://localhost:8000/docs` (dopo aver avviato il server e autenticato via browser).

## Contribuzione

Sentiti libero di clonare, modificare e contribuire.
