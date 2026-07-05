# Workflow

How I work in this repo, so the history stays clean and nothing lands broken.

## Branch, PR, merge

- I never commit straight to `main`. I branch off fresh `main`, make the change and open a pull request.
- I turn on auto-merge at creation: `gh pr merge --squash --auto --delete-branch`. The PR merges itself once CI passes, so I never sit and watch it.
- `main` is protected: the `check` CI job has to pass before a PR can merge. The rule is non-strict on purpose (I do not require a branch to be up to date first), because the strict version triggers a bot-push approval loop.
- One change is one branch is one PR. I keep unrelated work apart.

## Commits

- Conventional prefixes: `feat`, `fix`, `chore`, `ci`, `docs`.
- I write commit messages and PR descriptions in the first person and present tense, saying what the change does and why.
- UK English. No em dashes or en dashes. No Oxford comma, so I write "x, y and z".
- Script comments are first person too and explain the intent, not the obvious.

## Pushing

- `origin` mirrors to several hosts and is slow, so I push straight to GitHub: `git push https://github.com/zaccesss/isaac-adjei-automations.git HEAD:refs/heads/<branch>`.

## Before a PR

- Python: `python -m py_compile scripts/*.py` (CI runs `compileall`).
- Node: `node --check scripts/*.mjs`.
- I never commit a secret. Gitleaks scans every push.

## Secrets

- Every credential is an Actions secret, never in the code. A workflow maps the secret to an env var and the script reads it.
- A secret name cannot start with `GITHUB_` (GitHub reserves that prefix), so the GitHub Models token is `GH_MODELS_TOKEN`.

## Scheduled jobs

- The data jobs run on a cron and are safe to re-run: they upsert, never delete and never overwrite a value that is already good.
- AI calls try Groq, then Gemini, then OpenRouter, then GitHub Models. If every provider fails, the next scheduled run picks up whatever was missed.
