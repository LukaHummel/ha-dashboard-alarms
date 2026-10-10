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
- `tools/verify_release.py`: checks synchronized versions, README resources, and the newest changelog entry; accepts `--tag vX.Y.Z` for release validation.
- `tools/verify_hacs.py`: offline HACS layout, manifest, documentation, and brand checks.
- `.github/workflows/pylint.yml`: shared validation for PRs, main, and exact release tags.
- `.github/workflows/release.yml`: Release Please creates release PRs and draft releases after main validation, and explicitly dispatches release PR validation with the built-in token.
- `.github/workflows/publish-release.yml`: validates the exact draft release tag, uploads the verified manual ZIP, and publishes only after success; supports manual retry by tag.
- `release-please-config.json` and `.release-please-manifest.json`: release strategy and current version. The node strategy manages npm files; additional updaters manage the integration and README versions.
- `.github/HACS_SUBMISSION.md`: current HACS default-list requirements and submission evidence.
- `.commitlintrc.cjs`: Conventional Commit rules shared by local checks and CI.
- `brand/icon.svg` inside the integration: editable source for the bundled `brand/icon.png`.

## Development and validation

Run commands from the repository root in an activated virtual environment:

```sh
python -m pip install -r requirements-dev.txt
python -m pylint custom_components/dashboard_alarms tools
python -m ruff check custom_components tests tools
python -m pytest -q
python tools/verify_release.py
python tools/verify_hacs.py
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

The manifest uses `ical>=14.3.0` because Home Assistant also depends on this package; an exact integration pin would conflict with future core updates. Development requirements pin the tested version for reproducibility. Keep hassfest passing when changing dependencies.

Do not commit virtual environments, dependency folders, release ZIPs, caches, or credentials. Include a focused regression test when changing scheduling, persistence, permissions, or ownership behavior.

Every authored commit and PR title must follow Conventional Commits: `type(optional-scope): description`, with an optional `!` before the colon for a breaking change. Allowed types are `build`, `chore`, `ci`, `deps`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, and `test`. Examples: `fix(audio): reduce playback gaps`, `feat: add alarm controls`, and `feat(api)!: change the alarm API`. A `BREAKING CHANGE:` footer is also accepted. Use a blank line before the body or footer. Only Git-generated merge/revert messages are exempt from commit checks; PR titles never are. Autosquash temporary `fixup!`/`squash!` commits before merging.

CI checks each PR's title and all its commits, including release bot PRs. Editing the PR title reruns validation. Main pushes check only the newly pushed range, leaving pre-existing history intact. Manual and exact-tag validation check the latest commit. After `npm ci`, check an intended message with `echo 'fix: describe the change' | npm run lint:commits`, or a branch range with `npm run lint:commits -- --from origin/main --to HEAD`. Fix invalid messages before merging; do not bypass the check with an arbitrary non-conventional squash title. Use `npx commitlint` with the same arguments if your shell consumes npm's argument separator.

Release Please manages stable `X.Y.Z` versions, `vX.Y.Z` tags, and `CHANGELOG.md`. Keep its version annotations on `const.py` and the README resource examples intact. Do not update versions manually for ordinary changes. Review generated release notes for useful upgrade instructions; retain relevant release history only in the changelog.

Keep generated assets committed because HACS installs the tagged source directory. Draft releases must pass validation against their exact tag before publication. Release Please needs write permissions to manage its PRs, labels, drafts, and CI dispatch; validation jobs remain read-only. Do not move published tags or replace published releases with different code. Run HACS validation without ignored checks before submitting to `hacs/default`.
