# Runtime Transition Checklist

Date: 2026-04-24

This checklist captures the lowest-risk path from the current manual/demo deployment style to a cleaner future production model.

Current known state:

- Live Gunicorn is managed by `portal.service`.
- The installed service currently runs as `jlambertson`.
- The installed service uses `APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json`.
- That deployed config points at Amazon RDS `portal1` with `DB_SSLMODE=require`.
- The installed service starts from `/soft/django-cms-01/PROD`.
- `/soft/django-cms-01/PROD` currently resolves to this repo checkout.
- The repo checkout is currently owned primarily as `jlambertson:nogroup`, not `*:appdev`.
- Both `jlambertson` and `software` are in the `appdev` group.

For the latest verified database/content/runtime snapshot, see [CURRENT_STATE.md](./CURRENT_STATE.md).

## Step 1: Stabilize the Current Manual Dev Server

Goal: keep the server working while allowing `jlambertson` to continue manual development and GitHub work.

1. Keep `portal.service` running as `jlambertson` for now.
2. Do not switch the live service to `software` until runtime paths, `uv`, and ownership are aligned.
3. Treat `/soft/django-cms-01/PROD` as the live app path, since that is what the installed service uses.
4. Keep `/soft/django-cms-01/conf/portal.conf.dev.json` as the active runtime config path until infra code is ready.
5. Use the installed systemd service as the source of truth for Gunicorn behavior, not old shell wrappers or removed Gunicorn config templates.

## Step 2: Make the Repo Safe for Shared Manual Operations

Goal: allow collaboration without changing the live service user yet.

1. Change the repo tree group from `nogroup` to `appdev`.
2. Change the `.git` directory group from `nogroup` to `appdev`.
3. Keep the repo owner as `jlambertson` for now.
4. Ensure directories under the repo are group-writable and setgid so new files inherit `appdev`.
5. Ensure tracked files that need routine edits are group-writable where appropriate.
6. Verify that `software` can read and write the repo and `.git` metadata after the ownership adjustment.

## Step 3: Align Manual Django Commands with Live Runtime

Goal: make manual `manage.py` usage behave like the running service.

1. Make the production helper script use `APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json`.
2. Make the production helper script use `/soft/django-cms-01/PROD` as the working directory.
3. Make the production helper script use the same `uv` path or execution context as the installed service.
4. Confirm that manual commands run against the same Django settings and code path as the service.
5. Test at least `check`, `showmigrations`, and one harmless read-only command before relying on the helper script operationally.

## Step 4: Prepare the Future `software` Runtime Handoff

Goal: move from a manual dev-owned runtime to a cleaner production-owned runtime.

1. Install `uv` in a location intended for the final runtime user, or standardize on a shared executable path.
2. Remove any remaining live dependency on `/home/jlambertson/...` paths.
3. Decide whether the future model is:
   a. `software` owns the deployed release tree and `jlambertson` develops elsewhere, or
   b. both users share a writable deployment tree temporarily through `appdev`.
4. Prefer option `a` for long-term production safety.
5. Make sure `/soft/django-cms-01/run`, `/soft/django-cms-01/www`, and any log/output paths are writable by the final runtime user.
6. Confirm that the final runtime user can read the active config under `/soft/django-cms-01/conf`.

## Step 5: Introduce the Infra-Managed Model

Goal: transition from server-local manual conventions to repeatable deployment logic.

1. Move service, config, and runtime file ownership decisions into infra code.
2. Render the app config file from infra-managed deployment variables.
3. Render the systemd service from infra code.
4. Keep app-repo templates only if they are still the authoritative source.
5. Use tagged releases and a `PROD` symlink as the final deployment pattern when ready.
6. Separate developer checkouts from the deployed release tree once the infra path exists.

## Step 6: Cut Over Carefully

Goal: switch ownership and runtime behavior without breaking the site.

1. Make the ownership and path changes in a maintenance window or quiet period.
2. Validate the service unit file before restart.
3. Confirm the runtime user can start Gunicorn, create the socket, and read config.
4. Restart the service.
5. Verify service health, socket creation, logs, and a page load.
6. Keep rollback notes handy for restoring the prior service user and config path if needed.

## Definition of Done

The transition can be considered complete when all of the following are true:

- `software` can run the live service without depending on `jlambertson` paths.
- `jlambertson` can continue normal development in a non-production-owned checkout.
- The deployed service, config file, and ownership model are all defined in infra code.
- Manual Django commands use the same config and code path as the live service.
- The active release is clearly identified and can be rolled back cleanly.
