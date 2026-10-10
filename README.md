# Dashboard Alarms

Local alarms for Home Assistant, with a calendar entity, a touch-friendly dashboard card, and large ringing controls across the Home Assistant interface. Create one-time, daily, or selected-weekday alarms; play a sound on media players; and snooze or dismiss from any open panel.

Requires **Home Assistant 2026.10.0 or newer**. The integration includes its card and a three-second chime. Alarms are scheduled by Home Assistant and continue to work when the dashboard is closed.

## Installation

### HACS

Add [this repository](https://github.com/LukaHummel/ha-dashboard-alarms) to HACS as a custom repository with type **Integration**, then install **Dashboard Alarms**. It is not in the HACS default repository list.

### Manual

Download `dashboard-alarms-X.Y.Z.zip` from [GitHub Releases](https://github.com/LukaHummel/ha-dashboard-alarms/releases) or use the repository's `custom_components/dashboard_alarms` folder. Copy that folder into `/config/custom_components/`. The final path should be:

```text
/config/custom_components/dashboard_alarms/manifest.json
```

### Configure the integration and card

1. Restart Home Assistant.
2. Open **Settings → Devices & services → Add integration → Dashboard Alarms**.
3. Choose a calendar name, default media players, sound, snooze duration, and maximum ringing duration. Leave the player list empty for an events-only setup. Multiple alarm calendars are supported.
4. Find the calendar's entity ID in the integration's entities.
5. Add **Dashboard Alarms** through the dashboard card picker, or use the YAML below with your calendar's entity ID. Reload the browser after installation or an upgrade.

```yaml
type: custom:dashboard-alarms-card
entity: calendar.dashboard_alarms
title: Alarms
# max_height: 600  # Optional scrollable tile area height, in pixels
```

The integration registers its card resource automatically for storage-mode dashboards. If the card is missing, add `/dashboard_alarms/dashboard-alarms-card.js?v=0.1.1` under **Settings → Dashboards → Resources** as a **JavaScript module**. <!-- x-release-please-version -->

For YAML-managed resources, merge this into your existing configuration:

<!-- x-release-please-start-version -->
```yaml
lovelace:
  resources:
    - url: /dashboard_alarms/dashboard-alarms-card.js?v=0.1.1
      type: module
```
<!-- x-release-please-end -->

## Using alarms

- **New alarm** opens the editor. Set a time, first date, and repeat pattern. Names are generated automatically.
- The alarm's **switch** enables or disables its schedule. Disabling also ends ringing and cancels any snooze.
- **Edit alarm** changes the schedule or deletes it after confirmation.
- **Snooze** postpones the current ringing occurrence, defaulting to 10 minutes. **Dismiss** stops the occurrence or cancels a pending snooze. Recurring schedules stay enabled. A dismissed one-time alarm is automatically disabled; switching it on again schedules its saved time today if it is still ahead, otherwise tomorrow. Re-enabling a disabled one-time alarm uses this same next-time behavior even if its original date was further ahead.

Ringing opens a large dialog with **Snooze** and **Dismiss** buttons. The dialog is loaded globally, so it works on other dashboards and settings panels even when no alarm card is mounted or the card is scrolled out of view. It shows all currently ringing alarm calendars you can control and closes as they are snoozed, dismissed, or timed out. The browser or companion app must be open and connected for these controls; backend audio continues with the interface closed. Reload open clients after upgrading.

Times use Home Assistant's timezone and its 12/24-hour display preference. For recurring alarms, the first date is the earliest permitted date and may be in the past. During daylight saving transitions, nonexistent times are skipped and repeated times fire once at their first occurrence.

The bundled chime repeats every three seconds until snoozed, dismissed, or timed out. The default ring limit is 10 minutes. Sound, players, snooze duration, and ring limit can be overridden per alarm.

After a restart, missed occurrences are recorded without playing them. Future snoozes survive restarts; interrupted ringing is marked missed. The card shows the latest missed occurrence for each alarm.

## Sound and troubleshooting

Media players must support `play_media` and `media_stop`, and must be able to reach Home Assistant to fetch local audio. Set a reachable internal URL under **Settings → System → Network** if the bundled chime cannot be fetched.

Sounds can be local paths, HTTP(S) URLs, or media-source URIs. Custom clips replay when the player reports completion or the clip's reported duration elapses. Players that expose neither use a 15-second fallback; prefer the bundled chime or a player that reports playback state/duration. Network and device buffering can still add a small gap. Player volume is left unchanged, and previously playing music is not restored.

When alarms share a player, the most recently started alarm supplies the sound. Dismissing one alarm leaves the others ringing. A playback failure is shown in the card and emitted as an event; working targets continue.

| Symptom | Check |
| --- | --- |
| Card type is unknown | Check the module resource above, then reload the browser. |
| Calendar cannot be selected | Use the entity ID belonging to a Dashboard Alarms integration instance. |
| Alarm fires without sound | Check its player overrides, player availability, and access to the audio URL. An empty player list emits events only. |
| Ringing dialog is missing | Reload the open Home Assistant client after installing or upgrading, and check its connection. |

## Calendar and storage

Each integration instance owns a standard Home Assistant calendar. Enabled events are `confirmed`; disabled events are `tentative` and remain visible. The calendar entity's `on`/`off` state describes an active event, not whether an alarm is enabled. Standard calendar triggers can observe disabled events; use the lifecycle events below for alarm automations.

Native calendar editing supports timed events with once, daily, and selected-weekday patterns, including bounded `COUNT`/`UNTIL` rules. All-day events, monthly/yearly repeats, ordinal weekdays, and intervals other than 1 are rejected. Native instance and this-and-future edits use iCalendar exceptions. The card edits the complete schedule and saves recurring patterns without an end date.

Audio overrides are stored in the reserved `[dashboard_alarms:v1]` description block. Leave that block intact when editing events manually; ordinary description text is retained.

Schedules, occurrence history, and snooze state are stored locally and included in Home Assistant configuration backups. Reloading preserves them. Removing an integration instance deletes its stores.

## Automations

All services accept the alarm calendar's `entity_id`. Services other than `create_alarm` also require an alarm `uid`.

| Service | Additional data |
| --- | --- |
| `dashboard_alarms.create_alarm` | `alarm` definition; optionally returns its UID |
| `dashboard_alarms.update_alarm` | `alarm` with the complete definition |
| `dashboard_alarms.set_enabled` | `alarm: {enabled: true}` or `false` |
| `dashboard_alarms.delete_alarm` | No additional data |
| `dashboard_alarms.snooze` | Optional `minutes` |
| `dashboard_alarms.dismiss` | No additional data |

Example creation:

```yaml
action: dashboard_alarms.create_alarm
data:
  entity_id: calendar.dashboard_alarms
  alarm:
    start: '2026-10-12T07:00:00'  # Local time in Home Assistant's timezone
    repeat: weekdays           # once | daily | weekdays
    weekdays: [0, 2, 4]         # Monday=0, Sunday=6
    enabled: true
    description: Breakfast
    audio: {}                  # Use integration defaults
response_variable: alarm
```

Set `start` to your desired date; one-time alarms require a future time. Optional `audio` keys are `media_players` (list), `sound` (path/URL/media-source URI), `snooze_minutes`, and `ring_minutes` (whole numbers 1–120). Omitted keys inherit defaults; an explicit empty player list selects events-only operation.

Lifecycle events use type **`dashboard_alarms_event`**, with `action`, `entity_id`, `uid`, and action-specific details. Actions are `create`, `update`, `set_enabled`, `delete`, `fired`, `missed`, `snooze`, `dismiss`, `timed_out`, and `audio_error`. A `fired` event also includes `occurrence` and `snoozed`.

```yaml
triggers:
  - trigger: event
    event_type: dashboard_alarms_event
    event_data:
      action: fired
      entity_id: calendar.dashboard_alarms
actions:
  - action: light.turn_on
    target:
      entity_id: light.bedroom
mode: parallel
```

Authenticated WebSocket commands are `dashboard_alarms/list`, `dashboard_alarms/subscribe`, and `dashboard_alarms/command`. All require `entity_id`. Command additionally takes a service-name `command` and optional `uid`, `alarm`, and `minutes`. List and subscription updates include `entity_id`, `time_zone`, `defaults`, `can_control`, and all alarm definitions. Entity permissions apply to user-originated calls.

## Development

Use **Python 3.14.2 or newer**, matching the supported Home Assistant release. A Linux virtual environment is recommended for installing Home Assistant's dependencies. From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pylint custom_components/dashboard_alarms tools
python -m ruff check custom_components tests tools
python -m pytest -q
python tools/verify_release.py
python tools/verify_hacs.py
python tools/build.py
python tools/verify_archive.py
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. The build tools themselves only need Python 3.12 or newer and the standard library.

Pylint checks integration and build code, with project-specific settings in `pyproject.toml`. Ruff checks integration, tools, and tests. Backend tests use the real `ical` parser and Home Assistant adapter fakes.

For the card and global ringing dialog tests, install Node.js 22 or newer and the pinned Playwright dependency:

```sh
npm ci
npx playwright install chromium
npm test
```

Browser tests exercise the card and global dialog in Chromium with a mocked Home Assistant API, including controls without a mounted card, multiple calendars, reconnects, failures, and mobile layout. Neither suite replaces testing integration loading and audio on a real Home Assistant instance. Before relying on alarms, verify a one-time alarm with another panel open, snooze/dismiss, re-enabling, restart recovery, and your chosen players.

Build outputs are written to `outputs/`: an installation ZIP, a source ZIP, and a copy of this README. Contributor guidance is in [AGENTS.md](https://github.com/LukaHummel/ha-dashboard-alarms/blob/main/AGENTS.md).

## Releasing

Release versions use `X.Y.Z`, with Git tags named `vX.Y.Z`. HACS installs the files from the tagged integration directory; the attached ZIP is for manual installation. The card and ringing dialog ship with the integration, so they do not need separate releases.

1. Use [Conventional Commits](https://www.conventionalcommits.org/) for each commit and the PR title: `fix: reduce alarm playback gaps`, `feat: add alarm controls`, or `feat!: change the alarm API`. CI checks PR titles, all commits in a PR, and new commits pushed to `main`. Title edits rerun the check; existing project history is not checked again. Fixes produce patch releases; features produce minor releases. Before version 1.0, breaking changes also produce minor releases.
2. The **Release Please** workflow validates `main` and maintains a release PR. It updates the integration manifest, Python version constant, npm files, this README's resource versions, `.release-please-manifest.json`, and [CHANGELOG.md](CHANGELOG.md) together. Review the generated notes and add upgrade instructions when needed.
3. Wait for the release PR's **Validation** checks to pass, then merge it. Release Please creates the tag and a draft GitHub release. The publishing workflow reruns Python, Chromium, hassfest, and HACS checks against that exact tag, attaches the verified installation ZIP, and publishes the draft only after success.

Allowed commit types are `build`, `chore`, `ci`, `deps`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, and `test`, with an optional scope. A `BREAKING CHANGE:` footer also marks a breaking change. Check a message locally with `echo 'fix: describe the change' | npm run lint:commits`, or run `npm run lint:commits -- --from origin/main --to HEAD` for a branch. Standard Git merge/revert messages are exempt from commit checks; PR titles must use the conventional format.

The workflow uses the built-in `GITHUB_TOKEN`; no additional secret is needed. GitHub's **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests** must be enabled. The automation creates PRs and does not approve or merge them. It explicitly dispatches the Validation workflow on the release PR branch so its checks run without the approval needed for ordinary bot-created PR events. Other PR workflows may still show an approval prompt.

HACS offers published versions, with the default branch hidden. The release checks reject mismatched versions, missing changelog entries, generated assets that differ from committed files, and commits not merged into `main`. Keep generated assets committed because HACS installs the tagged source directory.

If publishing a draft fails, rerun **Publish release** from GitHub Actions with its `vX.Y.Z` tag. This reruns validation before publishing. Code fixes require a new release PR and version. Keep published tags unchanged and do not publish drafts manually before checks finish.

For submission to the HACS default repository list, use the verified requirements and submission details in [.github/HACS_SUBMISSION.md](.github/HACS_SUBMISSION.md).

## License

[Apache License 2.0](LICENSE).
