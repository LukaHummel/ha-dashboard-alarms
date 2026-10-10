from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntFlag, StrEnum
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from conftest import module
from test_manager import Audio
from custom_components.dashboard_alarms.manager import AlarmManager


class Features(IntFlag):
    CREATE_EVENT = 1
    DELETE_EVENT = 2
    UPDATE_EVENT = 4


class Status(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"


@dataclass
class CalendarEvent:
    start: datetime
    end: datetime
    summary: str
    description: str = ""
    uid: str = ""
    location: str = ""
    status: Status = Status.CONFIRMED
    rrule: str = None
    recurrence_id: str = None


class CalendarEntity:
    async def async_added_to_hass(self):
        pass

    async def async_will_remove_from_hass(self):
        pass

    def async_write_ha_state(self):
        self.writes = getattr(self, "writes", 0) + 1

    def async_update_event_listeners(self):
        self.pushes = getattr(self, "pushes", 0) + 1


module("homeassistant.components.calendar", CalendarEntity=CalendarEntity, CalendarEvent=CalendarEvent,
       CalendarEventFeature=Features, CalendarEntityFeature=Features, CalendarEventStatus=Status,
       EVENT_START="dtstart", EVENT_END="dtend")

from custom_components.dashboard_alarms.calendar import AlarmCalendarEntity  # noqa: E402


@pytest.mark.asyncio
async def test_calendar_crud_cache_status_and_live_notifications(hass):
    zone = ZoneInfo("Europe/Berlin")
    now = datetime(2026, 10, 10, 12, tzinfo=zone)
    entry = SimpleNamespace(entry_id="calendar-test", data={}, options={})
    manager = AlarmManager(hass, entry, Audio())
    manager.now = lambda: now
    await manager.load()
    entity = AlarmCalendarEntity(manager)
    entity.hass = hass
    entity.entity_id = "calendar.alarm_test"
    await entity.async_added_to_hass()
    await entity.async_create_event(dtstart=datetime(2026, 10, 11, 7, tzinfo=zone),
                                    dtend=datetime(2026, 10, 11, 7, 1, tzinfo=zone), rrule="FREQ=DAILY")
    uid = manager.definitions[0]["uid"]
    assert entity.event.uid == uid
    assert entity.extra_state_attributes["dashboard_alarms"]
    await manager.mutate("set_enabled", uid, {"enabled": False})
    events = await entity.async_get_events(hass, now, now + timedelta(days=3))
    assert len(events) == 3
    assert all(event.status == Status.TENTATIVE for event in events)
    await entity.async_update_event(uid, {"dtstart": "2026-10-11T08:00:00", "dtend": "2026-10-11T08:01:00", "rrule": "FREQ=DAILY"})
    assert entity.event.start.hour == 8
    manager.now = lambda: datetime(2026, 10, 11, 8, 1, tzinfo=zone)
    # The next cached event advances without IO or waiting for the heartbeat.
    assert entity.event.start.day == 12
    assert entity.writes and entity.pushes
    await entity.async_delete_event(uid)
    assert not manager.definitions
    await entity.async_will_remove_from_hass()
    await manager.close()
