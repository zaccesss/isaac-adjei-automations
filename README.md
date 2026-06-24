# automations

A small collection of scheduled jobs - nightly data syncs and timed reminders - that run on GitHub Actions.

Each job is a cron-scheduled workflow in [`.github/workflows`](.github/workflows) wrapping a short, self-contained script. The scripts are deliberately generic and take all of their runtime settings from the environment, so the repository can stay public (and free to run) without carrying anything sensitive.

## Jobs

| Workflow | Schedule | Purpose |
| --- | --- | --- |
| [routine](.github/workflows/routine.yml) | 07:00 Europe/London | Reads the day's habits and streaks and posts a morning checklist to Discord |

## Conventions

- One workflow per job, named for what it does.
- Scripts are configured entirely through the environment; nothing configurable is committed.
- A gitleaks scan runs on every push and pull request.
- Dependabot keeps the action versions current.

## Licence

See [LICENSE](LICENSE).
