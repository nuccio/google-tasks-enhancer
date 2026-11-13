# Security policy

## Reporting a vulnerability

Do not open a public issue. Use **Security → Report a vulnerability** on GitHub, which reaches the maintainer privately. This includes any way to read another user's tasks, tokens or session.

## Supported versions

Fixes go to `main`. Older commits are not patched.

## What the app holds

The backend stores each user's Google OAuth tokens in the local SQLite database (`backend/app.db`), currently in clear text, and signs the login session with `SECRET_KEY`. Anyone who can read that file or that key can act on the users' Google Tasks. The database file, `backend/.env` and any `client_secret*.json` / `credentials.json` are never committed.

## What protects the repository

| Control | What it covers |
|---|---|
| `.gitignore` for `.env`, `*.db`, `client_secret*.json`, `credentials.json` | accidental commits of credentials |
| Dependabot with a 7-day cooldown | outdated dependencies, grouped in few pull requests |
| Actions pinned to commit SHAs | the workflows that test the code |
| Branch rules on `main` (see `docs/maintainer-agent-workflow.md`) | unreviewed or unsigned changes |
