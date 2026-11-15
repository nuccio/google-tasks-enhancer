# Google Tasks Enhancer

Google Tasks Enhancer extends Google Tasks. It syncs your tasks from Google Tasks into a local database, adds custom fields to them (priority, project name, hashtags and estimated time) and keeps them up to date. The app has a FastAPI backend with a REST API and a scheduler for automatic sync, and a React frontend that the backend serves.

## Features

*   **Sync from Google Tasks (partial two-way):** Syncs tasks from Google Tasks into the local database.
*   **Custom fields:** Adds `priority`, `project_name`, `hashtags` (taken from the title) and `estimated_time_minutes` to the tasks.
*   **Google OAuth 2.0 sign-in:** Supports signing in with a Google account for several users (web application flow).
*   **SQLite database:** Uses SQLite for persistence, which is easy to set up and fine for development.
*   **REST API:** Exposes endpoints to manage the tasks.
*   **Automatic sync:** Syncs all registered users at start-up and then every 5 minutes.
*   **UI languages:** English (default) and Italian (see [UI languages](#ui-languages)).

### Data sync logic

The backend uses a "smart" sync to keep the local database up to date with Google Tasks:
1.  **Full fetch:** When a user signs in, or when the scheduler starts, the app fetches **all the tasks** (completed ones included) of the user from the Google Tasks API.
2.  **Incremental update:** Each task received from the API is compared with the version in the local database. If the task already exists, its fields are updated. If it is a new task, it is added.

#### Why completed tasks need special handling

We observed that, in some cases, the Google Tasks API does **not always return the tasks that were marked as "completed"** in the Google Tasks interface, even when the request explicitly asks for completed tasks (`showCompleted=True`). This creates a gap between the state the user sees and the data the API returns.

To keep the local data consistent, we use this strategy:
If a task is in our local database but is **not returned** by the Google Tasks API during a sync, the app assumes the user completed it. The task is then **automatically set to the "completed" status** in the local database, with a completion timestamp. This way the app reflects the right state of the tasks even when the Google API behaves unexpectedly or filters tasks implicitly.

## Architecture

The backend is built with **FastAPI** (Python), using **SQLAlchemy** as the ORM and **APScheduler** for background jobs. The frontend (`frontend/`) is a React + TypeScript app built with Vite; the API serves its production build.

Main components of `backend/`:
*   `main.py`: Entry point of the FastAPI app and its main endpoints.
*   `auth.py`: Google OAuth 2.0 authentication flow.
*   `database.py`: SQLite connection setup.
*   `models.py`: Database models for `User` and `Task`.
*   `crud.py`: CRUD (Create, Read, Update, Delete) operations on the database.
*   `scheduler.py`: Background sync of the tasks with Google Tasks.
*   `devui.py`: read-only dev API under `/dev/api` for the local data viewer, off by default (see [Local data viewer](#local-data-viewer-development-only)).
*   `alembic/`: database migrations.

## Setup and installation

To run the app locally, follow these steps:

### 1. Clone the repository

```bash
git clone https://github.com/nuccio/google-tasks-enhancer
cd google-tasks-enhancer
```

### 2. Set up the Google Cloud credentials

1.  **Google Cloud Console:** Go to [https://console.cloud.google.com/](https://console.cloud.google.com/).
2.  **Select or create a project:** Make sure you are in the right project.
3.  **Enable the API:** Go to `APIs & Services > Library` and enable the **"Google Tasks API"**.
4.  **Create OAuth 2.0 credentials:**
    *   Go to `APIs & Services > Credentials`.
    *   Click `Create credentials > OAuth client ID`.
    *   **Application type:** `Web application`.
    *   **Name:** `Google Tasks Enhancer Web App` (or similar).
    *   **Authorized redirect URIs:** Add `http://localhost:8000/auth/google`.
    *   Copy the **Client ID** and the **Client secret**: you need them in the next step. The app does not read the JSON file you can download from the console, so you do not need to save it in the project.

### 3. Set the environment variables

Copy `backend/env.example` to `backend/.env` and replace the placeholders with your values:

```bash
cp backend/env.example backend/.env
```

```dotenv
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
SECRET_KEY=A_LONG_RANDOM_SECRET_STRING_FOR_THE_FASTAPI_SESSIONS
```
*Make sure `SECRET_KEY` is a long random string, for example generated with `python3 -c "import secrets; print(secrets.token_hex(32))"`.*

> **Security:** `backend/.env` and any `client_secret*.json` / `credentials.json` file are excluded from git by `.gitignore`. Never commit real credentials.

### 4. Install the dependencies

Python 3.11 or later is required. From the repository root:

```bash
python3 -m pip install -r backend/requirements.txt
```

Node.js is needed for the frontend only if you want to change or rebuild it:

```bash
cd frontend && npm ci && npm run build
```

### 5. Update an existing database

**Skip this step on a fresh clone.** There is no `backend/app.db` yet: the app creates the tables when it starts for the first time (step 6). Running the commands below without a database creates an empty file, and `alembic upgrade head` then fails with `no such table: tasks`.

This step is only for a database that already exists, for example one created by an earlier version of the app. The app creates its tables at start-up but does not run Alembic, so run the migrations after you pull a new version of the code. The commands below use the database that `backend/alembic/env.py` points at, which is `backend/app.db`, the file that holds the users' Google tokens in clear text. Never commit it.

1.  Check which revision the database is at. This reads only the version table, not your data:

    ```bash
    cd backend && python3 -m alembic current
    ```

2.  If it shows no revision and the database was created by the app (not by Alembic), record the schema it already has, once:

    ```bash
    python3 -m alembic stamp fb815bf08509
    ```

3.  Back up the database first: copy `app.db` to a file whose name ends in `.db`, for example `app-backup.db`, so that git ignores the copy. From the `backend/` directory (where the commands above leave you): `cp app.db app-backup.db`. To restore, copy it back the same way. Then apply the migrations:

    ```bash
    python3 -m alembic upgrade head
    ```

The latest revision, `c3a91e7d5b24`, stores the task priorities with English values. It changes only data, not the schema: in the `priority` column of every task, `media`, `alta` and `bassa` (case and surrounding spaces ignored) become `medium`, `high` and `low`. All other values are left as they are. To go back, run `python3 -m alembic downgrade fb815bf08509`: it turns `medium`, `high` and `low` back into `media`, `alta` and `bassa`. The database does not record which rows the upgrade changed, so rows that were already English before the upgrade (set from the UI) also become Italian on downgrade.

### 6. Start the server

From the repository root (the variables are read from `backend/.env`):

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level debug
```
To stop the server, press `Ctrl+C`.

## UI languages

The UI is in English by default. Italian is available from the language selector in the header and on the login page.

- The choice is kept in the browser's `localStorage` under the key `gte.locale`. Nothing is sent to the server, and the browser's own language is not used.
- To add or change a text, edit both dictionaries, `frontend/src/i18n/en.ts` and `frontend/src/i18n/it.ts`. A key missing from one of them fails `npm run build`.
- The `/dev` data viewer is always in English.

## Running the checks

```bash
python3 -m pytest backend/tests     # from the repository root; needs backend requirements + pytest installed
cd frontend && npm test             # unit tests (Vitest)
cd frontend && npm run build        # type-check + build
cd frontend && npm run lint
```

CI runs these checks, and all of them are required checks: the backend tests run on Python 3.11, 3.12 and 3.13, and `Frontend build` runs `npm test` and then `npm run build`.

### Repository language check

Everything in the repository is written in English; the only Italian file is the UI dictionary `frontend/src/i18n/it.ts`. `backend/tests/test_repository_language.py` guards this. It runs over every tracked text file and looks for accented vowels and for a short list of distinctive Italian words, and it fails with the file, line and word it found. It is a safety net for the obvious cases, not proof that a file is English. An exception is one line with a reason in `EXCEPTIONS` in that test; the list `NOT_TRANSLATED_YET` is for files that wait for their translation and must stay empty.

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

## Usage

### Sign in

1.  Open your browser (preferably in a private window) and go to `http://localhost:8000/`.
2.  The app shows its login page. Use it to sign in with Google, with the Google account whose tasks you want to sync (make sure it is a test user configured in the Google Cloud Console).
3.  After signing in you are sent back to `/`, where the app shows your tasks.

### API endpoints

*   **`GET /`**: Serves the frontend application (any path that no other endpoint handles gets the same page, except unknown `/dev/api/*` paths, which answer `404`).
*   **`GET /auth/login/google`**: Starts the Google OAuth 2.0 sign-in flow.
*   **`GET /auth/google`**: Callback URL for the Google sign-in.
*   **`GET /auth/me`**: Returns the email of the signed-in user (requires authentication).
*   **`GET /tasks/`**: Returns all the synced tasks of the signed-in user.
*   **`POST /tasks/sync`**: Forces a manual sync of the tasks of the signed-in user.
*   **`PATCH /tasks/{id}`**: Updates the fields of a task. `priority` accepts `low`, `medium`, `high` or `null`; any other value is rejected with a `422` error. A change of `status` is also sent to Google Tasks.
*   **`GET /dev`** and **`GET /dev/api/*`**: local read-only data viewer, off by default and for development only (see [Local data viewer](#local-data-viewer-development-only)).

You can explore and try the endpoints in the interactive FastAPI documentation at `http://localhost:8000/docs` (after starting the server and signing in with the browser). The endpoints are grouped under the tags `Authentication`, `Tasks`, `General` and `Dev UI`.

## Contributing

Feel free to clone, change and contribute. See [CONTRIBUTING.md](CONTRIBUTING.md).
