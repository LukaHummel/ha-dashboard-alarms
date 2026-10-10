"""Constants for Dashboard Alarms."""

DOMAIN = "dashboard_alarms"
VERSION = "0.1.0"
PLATFORMS = ["calendar"]
STATIC_URL = "/dashboard_alarms"
CARD_URL = f"{STATIC_URL}/dashboard-alarms-card.js?v={VERSION}"
DEFAULT_SOUND = f"{STATIC_URL}/chime.wav"
DEFAULTS = {
    "name": "Dashboard alarms",
    "media_players": [],
    "sound": DEFAULT_SOUND,
    "snooze_minutes": 10,
    "ring_minutes": 10,
}
EVENT = "dashboard_alarms_event"
SIGNAL = "dashboard_alarms_updated"

