# Contributing

This page covers how a change gets to `main`. The project's new text is written in English: code, comments, commit messages, issues and pull requests.

## Before you start

- Look for an existing issue, or open one describing the problem or the feature. For anything larger than a small fix, agree on the direction in the issue before writing code.
- Security problems (for example a way to read another user's tasks or tokens) should not be reported in a public issue. Use **Security → Report a vulnerability** on GitHub, which reaches the maintainer privately.

## Setup

```bash
git clone https://github.com/nuccio/google-tasks-enhancer
```

```bash
cd google-tasks-enhancer
```

```bash
python3 -m pip install -r backend/requirements.txt pytest
```

```bash
python3 -m pytest backend/tests
```

For the frontend, run `npm ci` in `frontend/`. The credentials needed to run the app against Google are described in [README.md](README.md); never commit them.

## Making a change

1. Create a branch from `main`, one per issue, e.g. `fix/sync-keeps-custom-fields` or `issue-14-pagination`.
2. Add or update tests with the change. The backend unit tests must pass on Python 3.11-3.13, and `npm run build` must pass in `frontend/`.
3. Update the docs (`README.md`) when behaviour or configuration changes.
4. If you change the database model, add an Alembic migration. If you change dependencies, update the lock file (`frontend/package-lock.json`).
5. Open a pull request against `main`. Put `Fixes #N` in the description, so the issue is closed when the pull request is merged.

## Signed commits

`main` only accepts commits whose signature GitHub can verify. Sign your commits with GPG or SSH. With an SSH key:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

Then add the same public key on GitHub as a **Signing Key**: Settings → SSH and GPG keys → New SSH key → Key type: **Signing Key**. A key added only as an Authentication Key lets you push, but your commits still show up as unverified.

## Maintainer's Claude sessions

The Claude sessions of the maintainer follow [docs/maintainer-agent-workflow.md](docs/maintainer-agent-workflow.md), which does not apply to other contributors.

## Review and merge

A pull request can be merged when:

- the **Tests** workflow passes (`Backend tests` on Python 3.11, 3.12 and 3.13, and `Frontend build` are required checks);
- it has one approving review;
- the branch is up to date with `main`.

The author of a pull request updates its branch. Reviewers do not push to it or use **Update branch** (`gh pr update-branch`): `main` requires approval of the last push, so an approver who updates the branch loses their own approval.

Pull requests are merged with **squash and merge**. GitHub signs the squash commit, so it stays verified on `main`. With rebase, GitHub rewrites the commits without signing them.
