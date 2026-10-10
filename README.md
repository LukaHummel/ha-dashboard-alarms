# Dashboard Alarms

A local Home Assistant alarm integration with its own calendar and touch-friendly dashboard card. Version 0.1.0 targets Home Assistant 2026.10 or newer.

No View Assist, Browser Mod, input helpers, separate Local Calendar integration, or external frontend resources are required.

## Install

1. Extract the installation ZIP. Copy **`custom_components/dashboard_alarms`** into your Home Assistant **`/config/custom_components/`** directory. The final path must be `/config/custom_components/dashboard_alarms/manifest.json`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Dashboard Alarms**. Choose a calendar name, default media players, sound, snooze duration, and ring limit. The bundled chime is the default. More than one alarm calendar can be configured.
4. Find the new calendar's entity ID in the integration's entities. Use that ID in the card below. It may differ from the example.
5. Add a **Dashboard Alarms** card using the dashboard card picker. Storage-mode dashboard resources are registered automatically. Reload the browser after installation or an upgrade.

```yaml
type: custom:dashboard-alarms-card
entity: calendar.dashboard_alarms
title: Alarms
# max_height: 600
```

For YAML-managed resources, merge this into your existing Lovelace resource configuration:

```yaml
lovelace:
  resources:
    - url: /dashboard_alarms/dashboard-alarms-card.js?v=0.1.0
      type: module
```

If automatic registration fails, add the same URL with type **JavaScript module** under **Settings → Dashboards → Resources**. Do not duplicate an existing resource or top-level YAML section.

### HACS

The source layout and `hacs.json` are prepared for an Integration custom repository. Add **https://github.com/LukaHummel/ha-dashboard-alarms** to HACS as type **Integration**, install, and follow steps 2–5. Private repositories require access through your HACS GitHub account and may need manual installation if unavailable in HACS. This project is not submitted to the HACS default list.

## Use

Tap **New alarm**, adjust the hour/minute using the large buttons, select the first date, choose **Once**, **Daily**, or **Selected weekdays**, and save. Names are generated automatically. The editor closes after successful saving and stays open on failure.

An alarm's switch enables or disables it while retaining its calendar event and settings. Editing and deleting are available through **Edit alarm**. Deletion asks for confirmation and removes the complete schedule. Disable also ends active ringing and cancels snooze. A completed one-time alarm must be edited to a future date before it can be re-enabled.

The selected date is the earliest permitted date for recurring alarms. A past first date is allowed for repeats. Scheduling uses Home Assistant's timezone, regardless of the browser timezone, and the card follows Home Assistant's 12/24-hour preference. A nonexistent spring-transition time is skipped; an ambiguous autumn-transition time fires once at its first occurrence.

Ringing alarms expose **Snooze** and **Dismiss**. Snooze defaults to 10 minutes; it does not change the recurring schedule. Dismiss ends the current occurrence, or cancels a pending snooze. The next recurring alarm remains scheduled. The chime repeats every 15 seconds until acted on or until the ring limit (10 minutes by default).

The backend schedules alarms with the dashboard closed. After a restart it records missed occurrences without sounding them and schedules the next repeat. Future snoozes survive restarts; interrupted ringing is marked missed rather than replayed. The card shows the latest missed occurrence per alarm, including after extended downtime.

### Sound

Use media players that support `play_media` and `media_stop`. The players must be able to reach Home Assistant's configured local URL to fetch the bundled chime or another local sound. Configure the internal Home Assistant URL under Network settings if URL discovery cannot resolve a reachable address. URLs/media-source URIs can be selected globally or overridden in each alarm's editor.

The integration leaves player volume unchanged. It does not restore previously playing music. A repeat starts the selected sound again every 15 seconds, so choose a short clip. If multiple alarms share a player, one playback loop plays the most recently started alarm's sound; dismissing one does not stop remaining alarms. Target-specific playback failures are shown in the card and emitted as events; other targets continue.

Leaving the default player list empty creates an events-only setup. Per-alarm overrides can explicitly select an empty list as well. Configure separate automations for lights or notifications if desired.

## Calendar behavior and storage

The integration owns a standard Home Assistant calendar entity. Alarm definitions are authoritative iCalendar events with stable UIDs. Storage is local, through Home Assistant storage helpers, and is included in normal configuration backups. It does not access another integration's private storage.

Enabled events use `confirmed`; disabled events use `tentative`, and remain visible in the standard calendar. These statuses are set by the alarm API. The calendar's `on`/`off` state means that an event is currently active, not that an alarm is enabled. Standard calendar triggers can observe disabled/tentative events too; use the integration's lifecycle events when building alarm automations.

Native calendar creation/editing supports timed events and the same once/daily/selected-weekday recurrence patterns. New events use default audio settings and generated names. All-day events, monthly/yearly patterns, ordinal weekdays, and intervals other than 1 are rejected. Bounded daily/weekly `COUNT`/`UNTIL` rules are accepted through calendar editing. The card uses unbounded repeats when saving a recurring schedule.

Alarm-specific audio settings are stored in a versioned metadata block in the event description; user description text is retained. Do not manually change the reserved `[dashboard_alarms:v1]` block. Calendar instance edits/deletions and this-and-future changes use iCalendar exceptions. The card edits a full schedule, and shows a hint when exceptions exist.

Runtime occurrence history and snooze state are stored separately from schedule events. Disabling, editing, or deleting invalidates pending callbacks. Occurrences are recorded before audio playback to prevent duplicate execution. Unloading/reloading preserves both stores; explicitly removing an integration instance deletes its stores.

## Automation API

Services are `dashboard_alarms.create_alarm`, `update_alarm`, `set_enabled`, `delete_alarm`, `snooze`, and `dismiss`. Each accepts `entity_id` for the alarm calendar. All except create also require `uid`. Create/update take an `alarm` object; update supplies a complete definition. Responses optionally return the UID.

```yaml
action: dashboard_alarms.create_alarm
data:
  entity_id: calendar.dashboard_alarms
  alarm:
    start: '2026-10-12T07:00:00' # Floating local time in Home Assistant's timezone
    repeat: weekdays           # once | daily | weekdays
    weekdays: [0, 2, 4]         # Monday=0, Sunday=6
    enabled: true
    description: Breakfast
    audio: {}                  # Empty uses integration defaults
response_variable: alarm
```

Choose a future date if using `repeat: once`. Optional `audio` keys are `media_players` (list), `sound` (URL/path/media-source URI), `snooze_minutes`, and `ring_minutes` (whole numbers 1–120). Omitted keys inherit defaults.

```yaml
action: dashboard_alarms.set_enabled
data:
  entity_id: calendar.dashboard_alarms
  uid: 'UID returned by create or list'
  alarm:
    enabled: false
```

`snooze` optionally accepts `minutes`. `dismiss` and `delete_alarm` need only calendar ID and UID.

Lifecycle events use event type **`dashboard_alarms_event`**. Data includes `action`, `entity_id`, `uid`, and action-specific details. Actions include create, update, set_enabled, delete, fired, missed, snooze, dismiss, timed_out, and audio_error. The fired event includes `occurrence` and `snoozed`.

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

The authenticated WebSocket commands are `dashboard_alarms/list`, `/subscribe`, and `/command`. All take `entity_id`; command takes a service-name `command` plus optional `uid`, `alarm`, and `minutes`. List and subscribe return `entity_id`, `time_zone`, `defaults`, and all alarm definitions, including disabled/completed alarms. Read/control entity permissions apply to WebSocket calls and user-originated services.

## Cutover from the old View Assist setup

This version starts fresh and does not import or delete View Assist alarms. Before recreating alarms here, disable the old **Dashboard – repeat View Assist alarms** automation and cancel its pending alarms. Replace the old dashboard card with this card. The old package and its draft helpers can then be removed if nothing else uses them. View Assist itself can remain installed for other functions.

## Validation

Backend tests use the real `ical` parser/event store and lightweight Home Assistant adapter fakes. They cover calendar persistence, recurrence and exceptions, DST, scheduling races, restart recovery, save failures, snooze, timeout, and shared-player ownership. Browser tests exercise the actual card in Chromium with a mocked API, including save errors, toggles, duplicate submission, reconnects, and responsive layouts. These are not a full Home Assistant integration-load test or a real-speaker test.

Before relying on this first release, test on your Home Assistant instance:

1. Create a one-time alarm two minutes ahead, close the dashboard, and verify sound.
2. Snooze it, verify it rings again, and dismiss it.
3. Create a recurring alarm, disable it, restart Home Assistant, and verify the saved disabled tile remains. Enable it and confirm its next occurrence.
4. Schedule two alarms sharing a player; dismiss one and verify the other continues.
5. Test a missing player and verify the error appears while a working target still rings.
6. Inspect the standard calendar, create/edit a timed event there, and verify the card updates.

### Development

Install `ical==14.1.1`, `probatio`, `pytest`, `pytest-asyncio`, and `ruff` into a Python environment. Run `pytest` and `ruff check custom_components tests tools`. Browser tests require Node.js and Playwright with Chromium. Run `node tests/card.spec.cjs`; optionally set `PLAYWRIGHT_MODULE` to an installed Playwright module path. Build the archive with `python tools/build.py`.

The repository contains no live Home Assistant credentials. The archive includes only the integration, its assets, documentation, example card, license, and HACS metadata.
