# google-tasks-enhancer

Syncs Google Tasks into a local SQLite database and adds custom fields (priority, project, hashtags, estimated time). FastAPI backend (`backend/`), React + Vite frontend (`frontend/`). Python >=3.11.

## Language

- **Talk to the maintainer in Italian**: replies, questions, explanations, summaries in chat.
- **Everything new written into the project is in English**: documentation, issues, pull requests, commit messages, log messages, code comments, docstrings, identifiers and error messages. `README.md` and older code comments are still in Italian; translate them only when you touch them for another reason.

## Commands

```bash
python3 -m pip install -r backend/requirements.txt pytest   # backend + test dependencies
python3 -m pytest backend/tests                             # unit tests, from the repository root
python3 -m uvicorn backend.main:app --reload                # API on http://localhost:8000, needs backend/.env
cd backend && python3 -m alembic upgrade head               # apply database migrations
cd frontend && npm ci                                       # frontend dependencies
cd frontend && npm run dev                                  # Vite dev server
cd frontend && npm run build                                # type-check + build, served by the API from frontend/dist
cd frontend && npm run lint
```

After changing the model in `backend/models.py`, add an Alembic migration in `backend/alembic/versions/`. After changing dependencies, update `backend/requirements.txt` or `frontend/package.json` and the lock file.

## Layout

- `backend/`: `main.py` (FastAPI app and endpoints), `auth.py` (Google OAuth), `scheduler.py` (sync with Google Tasks, token handling), `crud.py`, `models.py`, `database.py`, `alembic/` (migrations), `tests/`.
- `frontend/src/`: `api.ts` (calls to the API), `App.tsx`, `TaskTable.tsx`, `TaskRow.tsx`, `Header.tsx`, `LoginView.tsx`.
- `docs/maintainer-agent-workflow.md`: the rules of the maintainer's Claude sessions.

## Rules that matter

- **Never commit or print secrets**: `backend/.env`, `client_secret*.json`, `credentials.json`, `token.json`, and any `*.db` file (`backend/app.db` holds the users' Google tokens in clear text). Only `backend/env.example` is tracked, with placeholders. Don't read real credential or database files.
- Never log tokens, task titles or notes.
- Google OAuth scopes stay as narrow as the features need. Widening them needs an issue agreed with the maintainer. See `SECURITY.md`.
- Add tests with every change; the backend unit tests must pass on Python 3.11-3.13.
- Update `README.md` when behaviour or configuration changes.

## Workflow

- One branch per issue from `main`; PR against `main` with `Fixes #N`; squash and merge. Commits must be signed. Details in `CONTRIBUTING.md`. Sessions whose preset sets `AGENT_ROLE` use the branch model of `docs/maintainer-agent-workflow.md` instead.
- In the maintainer's sessions, check the identity before pushing: `gh api user --jq .login` (or `get_me` of the GitHub MCP tools where `gh` is not installed) must print `$AGENT_GH_LOGIN`. Without that variable, or on a mismatch, the session has no role and does not push, approve or merge.
- Don't push, merge or touch `main` without an explicit request. A coordinator's scope, given by the maintainer, is the explicit request for merging inside that scope, and only for that.

## Agent workflow

A session follows `docs/maintainer-agent-workflow.md` when its preset sets `AGENT_ROLE`. The roles, scope, merge conditions and stop conditions are there.

- A coordinator works alone inside its scope, one approved issue plus its sub-issues: `gh pr merge` and `gh pr review` are not under `ask`. Permission patterns cannot tell a PR's base branch apart, so "a coordinator never approves or merges a PR to `main`" is a written rule.
- Protected areas: a coordinator may merge into the issue branch a PR touching the protected paths listed in that file only when the approved design declares the area, the security check passed and the diff stays inside the declared areas. Changes to `SECURITY.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/maintainer-agent-workflow.md`, `.claude/` and `.github/` reach `main` only through the final PR.
- Never: push to `main`, use `--admin`, change branch protection or rulesets or these rules, create issues outside the scope, read or print credentials.
