"""Calendar platform for Dashboard Alarms."""

from datetime import timedelta

from homeassistant.components.calendar import (
    EVENT_END, EVENT_START, CalendarEntity, CalendarEntityFeature, CalendarEvent, CalendarEventStatus,
)
from homeassistant.exceptions import HomeAssistantError

from .model import local_datetime


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AlarmCalendarEntity(entry.runtime_data)], True)


def calendar_data(event):
    """HA calendar writes use dtstart/dtend; the alarm API uses start/end."""
    data = dict(event)
    if EVENT_START in data:
        data["start"] = data.pop(EVENT_START)
    if EVENT_END in data:
        data["end"] = data.pop(EVENT_END)
    return data


class AlarmCalendarEntity(CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:alarm"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.UPDATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(self, manager):
        self.manager = manager
        self._attr_unique_id = manager.entry.entry_id
        self._attr_name = manager.settings["name"]
        self._cached_events = []

    @property
    def event(self):
        now = self.manager.now().timestamp()
        return next((event for event in self._cached_events if event.end.timestamp() > now), None)

    @property
    def extra_state_attributes(self):
        return {"dashboard_alarms": True, "alarm_count": len(self.manager.definitions)}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.manager.entity_id = self.entity_id
        self.manager.calendar_entity = self
        await self.manager.start()

    async def async_will_remove_from_hass(self):
        self.manager.calendar_entity = None
        await super().async_will_remove_from_hass()

    def _convert(self, when, event):
        end = local_datetime(event.end, self.manager.model.zone)
        if end.timestamp() <= when.timestamp():
            end = when + timedelta(minutes=1)
        status = CalendarEventStatus.TENTATIVE if event.status.value.lower() == "tentative" else CalendarEventStatus.CONFIRMED
        return CalendarEvent(start=when, end=end, summary=event.summary or "Alarm", description=event.description,
                             uid=event.uid, location=event.location, status=status,
                             rrule=event.rrule.as_rrule_str() if event.rrule else None,
                             recurrence_id=event.recurrence_id)

    async def refresh(self):
        now = self.manager.now()
        def upcoming():
            current = self.manager.model.occurrences(now, now + timedelta(minutes=1))
            choices = [(when, event) for when, event in current
                       if local_datetime(event.end, self.manager.model.zone).timestamp() > now.timestamp()]
            for root in self.manager.model.roots():
                next_event = self.manager.model.next_occurrence(root.uid, now)
                if next_event:
                    choices.append(next_event)
                    following = self.manager.model.next_occurrence(root.uid, next_event[0])
                    if following:
                        choices.append(following)
            return sorted(choices, key=lambda item: item[0].timestamp())
        upcoming_events = await self.hass.async_add_executor_job(upcoming)
        self._cached_events = [self._convert(*item) for item in upcoming_events]
        if self.entity_id:
            self.async_write_ha_state()
            self.async_update_event_listeners()

    async def async_update(self):
        # The manager refreshes the cached calendar after every mutation and heartbeat.
        if self.hass and self.manager.model:
            await self.refresh()

    async def async_get_events(self, hass, start_date, end_date):
        events = await hass.async_add_executor_job(self.manager.model.occurrences, start_date, end_date)
        return [self._convert(*item) for item in events]

    async def async_create_event(self, **kwargs):
        try:
            await self.manager.mutate("create", data=calendar_data(kwargs), calendar_api=True)
        except Exception as err:
            raise HomeAssistantError(str(err)) from err

    async def async_update_event(self, uid, event, recurrence_id=None, recurrence_range=None):
        await self.manager.mutate("update", uid, calendar_data(event), calendar_api=True,
                                  recurrence_id=recurrence_id, recurrence_range=recurrence_range)

    async def async_delete_event(self, uid, recurrence_id=None, recurrence_range=None):
        await self.manager.mutate("delete", uid, recurrence_id=recurrence_id, recurrence_range=recurrence_range)

