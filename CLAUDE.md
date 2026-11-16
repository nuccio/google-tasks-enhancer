# google-tasks-enhancer

Syncs Google Tasks into a local SQLite database and adds custom fields (priority, project, hashtags, estimated time). FastAPI backend (`backend/`), React + Vite frontend (`frontend/`). Python >=3.11.

## Language

- **Talk to the maintainer in Italian**: replies, questions, explanations, summaries in chat.
- **Everything written into the repository is in English**: documentation, issues, pull requests, commit messages, log messages, code comments, docstrings, identifiers and error messages. Italian is used only in the conversation with the maintainer. `frontend/src/i18n/it.ts` is the only Italian file.

## Commands

```bash
python3 -m pip install -r backend/requirements.txt pytest   # backend + test dependencies
python3 -m pytest backend/tests                             # unit tests, from the repository root
python3 -m uvicorn backend.main:app --reload                # API on http://localhost:8000, needs backend/.env
cd backend && python3 -m alembic current                    # database revision (reads only the version table)
cd backend && python3 -m alembic stamp fb815bf08509         # only if no revision is shown and the app created the database
cd backend && python3 -m alembic upgrade head               # apply database migrations
cd frontend && npm ci                                       # frontend dependencies
cd frontend && npm run dev                                  # Vite dev server
cd frontend && npm test                                     # frontend unit tests (Vitest)
cd frontend && npm run build                                # type-check + build, served by the API from frontend/dist
cd frontend && npm run lint
```

After changing the model in `backend/models.py`, add an Alembic migration in `backend/alembic/versions/`. After changing dependencies, update `backend/requirements.txt` or `frontend/package.json` and the lock file.

## Layout

- `backend/`: `main.py` (FastAPI app and endpoints), `auth.py` (Google OAuth), `scheduler.py` (sync with Google Tasks, token handling), `crud.py`, `models.py`, `database.py`, `devui.py` (read-only dev API under `/dev/api` for the local data viewer), `alembic/` (migrations), `tests/`.
- `frontend/src/`: `api.ts` (calls to the API), `App.tsx`, `TaskTable.tsx`, `TaskRow.tsx`, `Header.tsx`, `LoginView.tsx`, `LanguageSelect.tsx` (language selector).
- `frontend/src/i18n/`: the UI dictionaries (`en.ts`, `it.ts`), the provider and the helpers.
- `frontend/dev.html`: the local data viewer page, served at `/dev`; its code is in `frontend/src/dev/`, separate from the app.
- `docs/maintainer-agent-workflow.md`: the rules of the maintainer's Claude sessions.

## Rules that matter

- **Never commit or print secrets**: `backend/.env`, `client_secret*.json`, `credentials.json`, `token.json`, and any `*.db` file (`backend/app.db` holds the users' Google tokens in clear text). Only `backend/env.example` is tracked, with placeholders. Don't read real credential or database files.
- Never log tokens, task titles or notes.
- Google OAuth scopes stay as narrow as the features need. Widening them needs an issue agreed with the maintainer. See `SECURITY.md`.
- `backend/tests/test_repository_language.py` fails when a tracked file contains Italian, outside its exceptions (`frontend/src/i18n/it.ts`, the test itself and `frontend/package-lock.json`). Fix the text; an exception is one line with a reason in that test.
- Add tests with every change; the backend unit tests must pass on Python 3.11-3.13.
- Update `README.md` when behaviour or configuration changes.

## Workflow

- One branch per issue from `main`; PR against `main` with `Fixes #N`; squash and merge. Commits must be signed. Details in `CONTRIBUTING.md`. Sessions whose preset sets `AGENT_ROLE` use the branch model of `docs/maintainer-agent-workflow.md` instead.
- In the maintainer's sessions, check the identity before pushing: `gh api user --jq .login` (or `get_me` of the GitHub MCP tools where `gh` is not installed) must print `$AGENT_GH_LOGIN`. Without that variable, or on a mismatch, the session has no role and does not push, approve or merge.
- Don't push, merge or touch `main` without an explicit request. A coordinator's scope, given by the maintainer, is the explicit request for merging inside that scope, and only for that.

## Agent workflow

A session follows `docs/maintainer-agent-workflow.md` when its preset sets `AGENT_ROLE`. The roles, scope, merge conditions and stop conditions are there. The maintainer takes part only at the issue approval, the design approval and the final PR to `main`.

- A coordinator works alone inside its scope, one approved issue plus its sub-issues: `gh pr merge` and `gh pr review` are not under `ask`. Permission patterns cannot tell a PR's base branch apart, so "a coordinator never approves or merges a PR to `main`" is a written rule.
- Hard stops: the coordinator waits for the maintainer only for cloud costs, Google OAuth scopes and anything stored about users, a database migration that drops or rewrites user data, a new external service, a communication outside the repository, credentials, a departure from the approved design, a problem found by the security check, a used-up retry limit, or anything else the final PR cannot undo or that has effects outside the repository. Every other decision it takes itself and records for the final report ("Decisions taken without the maintainer"); in doubt whether a decision is a hard stop, it stops. Every hard stop sends an in-app notification and is recorded under "Interruptions".
- Retry limit: 5 pushes per PR to fix failing checks, 5 review rounds, 5 attempts to start a session on the required model.
- Small-issue path: an issue whose approved design declares no protected area and a single implementation step, and says it takes this path, is done by one worker in one PR straight to `main` (`issue/<N>/impl-1`, `Fixes #N`, documentation and project memory included), with no issue branch. Otherwise the full path applies, and `main` is merged into the issue branch once, right before the final PR, only if it is behind.
- Protected areas: a coordinator may merge into the issue branch a PR touching the protected paths listed in that file only when the approved design declares the area, the security check passed and the diff stays inside the declared areas. Changes to `SECURITY.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/maintainer-agent-workflow.md`, `.claude/` and `.github/` reach `main` only through the final PR.
- Session models: the coordinator, the design worker, the security check and the reviewers run on Opus, the other workers on Sonnet. The coordinator sets the model of each worker and of the security check explicitly and checks it after the start; a missing or wrong model is retried, within the retry limit, and never replaced by another model. See "Session models" in `docs/maintainer-agent-workflow.md`.
- Permissions: the presets of both roles use Auto mode, which judges every command not under `deny` or `ask`; `.claude/settings.json` has no `allow` entries, `ask` for the write forms of `gh api`, and `deny` for the common forms of the dangerous commands and for the Claude in Chrome tools. The presets also set `SSH_AUTH_SOCK=/dev/null` and `GIT_SSH_COMMAND=/usr/bin/false`: a session never uses SSH or the owner's credentials.
- Never: push to `main`, use `--admin`, delete a branch unless the maintainer explicitly asks for it (every role, since the role tokens can delete `issue/<N>/base`), change branch protection or rulesets or these rules, create issues outside the scope, create a repository or a fork, read or print credentials.
