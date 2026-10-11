# Changelog

## [0.2.0](https://github.com/LukaHummel/ha-dashboard-alarms/compare/v0.1.1...v0.2.0) (2026-10-11)


### Features

* add brand icon image ([689ebd9](https://github.com/LukaHummel/ha-dashboard-alarms/commit/689ebd9046e638696036746ed2435a48efe9ec8b))
* automate releases and add HACS validation ([3360be8](https://github.com/LukaHummel/ha-dashboard-alarms/commit/3360be8618d7d4e7d6c5d94eae58c332c71cc525))

## 0.1.1 (2026-10-10)

- Create one-time, daily, and weekday alarms through a calendar and dashboard card.
- Snooze or dismiss ringing alarms from a large dialog on any open Home Assistant panel.
- Dismissing a one-time alarm disables it. Re-enabling schedules its saved time today or tomorrow.
- The bundled chime repeats every three seconds. Custom clips use player duration or completion state when available.
- Preserve future snoozes across restarts and coordinate alarms sharing a media player.

Requires Home Assistant 2026.10.0 or newer. Restart Home Assistant after installation or an upgrade, then reload open browser and companion-app clients.
