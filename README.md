# automations

A collection of scheduled jobs - data syncs, timed reminders and digests - that run on GitHub Actions and back my dashboard at [isaacadjei.me](https://isaacadjei.me).

Each job is a cron-scheduled workflow in [`.github/workflows`](.github/workflows) wrapping a short, self-contained script in [`scripts`](scripts). The scripts are deliberately generic and take all of their runtime settings from the environment, so the repository can stay public (and free to run) without carrying anything sensitive.

## Contents

- [`.github/workflows/README.md`](.github/workflows/README.md) - every workflow, its schedule and how the UK-time two-cron pattern works.
- [`scripts/README.md`](scripts/README.md) - what each script does and the environment it needs.

## Conventions

- One workflow per job, named for what it does; the workflow is a thin wrapper and the logic lives in the script.
- Scripts are configured entirely through the environment; nothing configurable is committed.
- Time-of-day jobs hold a fixed UK wall-clock time year-round via a two-cron GMT/BST gate; see the [workflows README](.github/workflows/README.md#uk-time-and-the-two-cron-pattern).
- A gitleaks scan runs on every push and pull request.
- Dependabot keeps the action versions current.

## Licence

See [LICENSE](LICENSE).
