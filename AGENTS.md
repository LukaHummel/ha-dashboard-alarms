# Repository guide

Dashboard Alarms is a local Home Assistant custom integration with a bundled dashboard card. It targets Home Assistant 2026.10.0 and newer. Full development tooling requires Python 3.14.2 or newer; CI runs on Ubuntu with Python 3.14.

## Layout

- `custom_components/dashboard_alarms/model.py`: iCalendar definitions, recurrence, validation, and timezone handling. This module is independent of Home Assistant.
- `manager.py`: persistent runtime state, occurrence scheduling, snooze, restart recovery, and lifecycle events.
- `audio.py`: playback loops and ownership of shared media players across integration instances.
- `calendar.py`: the Home Assistant calendar adapter.
- `api.py`: authenticated services and WebSocket commands.
- `config_flow.py` and `__init__.py`: configuration and integration lifecycle.
- `frontend/dashboard-alarms-card.js`: the card and its editor; plain JavaScript with no frontend build step.
- `frontend/dashboard-alarms-notifications.js`: globally registered ringing dialog, independent of any mounted card. Discovers the frontend root's connection/calendars and receives alarm changes through WebSockets.
- `tests/`: backend tests with Home Assistant adapter fakes and a separate Chromium card test.
- `tools/build.py`: generates translation/service metadata and the chime, then creates installation and source ZIPs under `outputs/`.
- `tools/verify_archive.py`: validates the installation ZIP.

## Development and validation

Run commands from the repository root in an activated virtual environment:

```sh
python -m pip install -r requirements-dev.txt
python -m pylint custom_components/dashboard_alarms tools
python -m ruff check custom_components tests tools
python -m pytest -q
python tools/build.py
python tools/verify_archive.py
```

Use the supported Home Assistant Python version and install its dependencies before running Pylint. Pylint checks integration/build code; Ruff also checks the tests. Keep import and error checks enabled. Any additional suppression should be narrow and explain a framework limitation.

For frontend changes, use Node.js 22 or newer, install pinned dependencies with `npm ci`, install Chromium with `npx playwright install chromium`, and run `npm test`. The tests support `PLAYWRIGHT_MODULE` and `PLAYWRIGHT_EXECUTABLE` overrides. Generated screenshots stay under `outputs/previews/`. `npm run preview:alarms` starts a mocked settings-panel shell for visual inspection on port 8124.

Run checks relevant to the change. Backend fakes and mocked browser tests do not replace a real Home Assistant load test or speaker playback test. State that limitation when reporting validation.

## Behavioral constraints

- Treat iCalendar storage as the authoritative schedule; runtime history and snooze state live in a separate store.
- Save definitions before committing them in memory, and record handled occurrences before audio playback. Preserve rollback and duplicate-fire protection.
- Use Home Assistant's timezone. Preserve DST behavior: skip nonexistent local times and fire ambiguous times once at the first occurrence.
- Disabling, editing, and deleting invalidate pending callbacks. Preserve future snoozes across restarts and avoid replaying interrupted ringing.
- Dismissing a one-time alarm durably disables it. Re-enabling a disabled one-time alarm selects the next occurrence of its saved local time, today or tomorrow, skipping nonexistent DST times. Repeated enable calls must not move an already-enabled schedule. Snoozing retains the enabled schedule; recurring dismissal retains the next occurrence.
- Preserve calendar and media-player permissions for user-originated service/WebSocket calls. Internal automations use the existing service context behavior.
- Preserve shared-player ownership so dismissing one alarm cannot silence another.
- Keep global ringing controls independent of card/panel mounting. Handle reconnects, multiple calendars, command failures, and late subscription responses without duplicate controls or leaked subscriptions.
- Keep the reserved `[dashboard_alarms:v1]` metadata compatible with stored events and retain user descriptions.
- Unload/reload preserves storage; explicit integration removal deletes the instance's stores.

## Maintenance

Keep the README focused on current installation, use, APIs, and development. Avoid obsolete migration notes, personal setup details, or project history.

When changing generated strings, services, or the chime, edit `tools/build.py` and regenerate the checked-in assets. Check the resulting diff. Keep version references in `const.py`, `manifest.json`, `package.json`/its lockfile, and resource examples consistent when releasing; archive filenames derive from the manifest. Keep the minimum Home Assistant version in `hacs.json`, `requirements-dev.txt`, and documentation consistent.

Do not commit virtual environments, dependency folders, release ZIPs, caches, or credentials. Include a focused regression test when changing scheduling, persistence, permissions, or ownership behavior.
