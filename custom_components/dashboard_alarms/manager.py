"""Persistent alarm calendar and server-side occurrence scheduler."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from homeassistant.core import callback
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULTS, DOMAIN, EVENT
from .model import AlarmCalendar

_LOGGER = logging.getLogger(__name__)


class AlarmManager:
    def __init__(self, hass, entry, audio):
        self.hass, self.entry, self.audio = hass, entry, audio
        self.settings = DEFAULTS | entry.data | entry.options
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.calendar")
        self.runtime_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.runtime")
        self.model = None
        self.runtime = {"alarms": {}, "last_checked": None}
        self.entity_id = None
        self.calendar_entity = None
        self.definitions = []
        self.listeners = set()
        self.callbacks = {}
        self.lock = asyncio.Lock()
        self.closed = False
        self.heartbeat = None
        self.config_listener = None

    def now(self):
        return dt_util.now().astimezone(ZoneInfo(self.hass.config.time_zone))

    async def load(self):
        data = await self.store.async_load()
        self.model = await self.hass.async_add_executor_job(
            AlarmCalendar, self.hass.config.time_zone, data.get("ics") if data else None
        )
        stored = await self.runtime_store.async_load()
        if stored:
            self.runtime = stored
        self.heartbeat = async_track_time_interval(self.hass, self._heartbeat, timedelta(minutes=1))
        self.config_listener = self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._heartbeat)

    async def start(self):
        """Called after the calendar entity is available."""
        async with self.lock:
            now = self.now()
            checked = self.runtime.get("last_checked")
            if checked:
                since = datetime.fromisoformat(checked)
                def missed_occurrences():
                    return [item for root in self.model.roots()
                            if (item := self.model.last_occurrence(root.uid, since, now))]
                missed = await self.hass.async_add_executor_job(missed_occurrences)
                for when, event in missed:
                    state = self.runtime["alarms"].setdefault(event.uid, {})
                    if when.timestamp() > float(state.get("handled", 0)):
                        state.update(handled=when.timestamp(), last_missed=when.isoformat(), state="missed")
                        self.emit("missed", event.uid, occurrence=when.isoformat())
            for state in self.runtime["alarms"].values():
                if state.get("state") == "ringing":
                    state.update(state="missed", last_missed=state.get("ring_started"))
                snooze = state.get("snooze_until")
                if snooze and datetime.fromisoformat(snooze).timestamp() <= now.timestamp():
                    state.update(state="missed", last_missed=snooze)
                    state.pop("snooze_until", None)
            self.runtime["last_checked"] = now.isoformat()
            await self._save_runtime()
            await self._refresh()

    def token(self, uid):
        return f"{self.entry.entry_id}:{uid}"

    async def close(self):
        async with self.lock:
            self.closed = True
            if self.heartbeat:
                self.heartbeat()
            if self.config_listener:
                self.config_listener()
            self._clear_callbacks()
            for uid in self.runtime["alarms"]:
                await self.audio.release(self.token(uid))
            self.listeners.clear()

    async def _save_runtime(self):
        await self.runtime_store.async_save(copy.deepcopy(self.runtime))

    @callback
    def _heartbeat(self, _):
        if not self.closed:
            self.hass.async_create_task(self._tick())

    async def _tick(self):
        async with self.lock:
            if self.closed:
                return
            try:
                self.runtime["last_checked"] = self.now().isoformat()
                await self._save_runtime()
                # Also reconciles timezone changes and bounds callback lifetimes.
                if str(self.model.zone) != self.hass.config.time_zone:
                    self.model.zone = ZoneInfo(self.hass.config.time_zone)
                await self._refresh()
            except Exception:
                _LOGGER.exception("Could not reconcile alarm calendar")

    async def mutate(self, operation, uid=None, data=None, **kwargs):
        data = data or {}
        async with self.lock:
            if self.closed:
                raise HomeAssistantError("The alarm calendar is unloading. Retry shortly.")
            try:
                candidate = await self.hass.async_add_executor_job(self.model.clone)
                if operation == "create":
                    uid = await self.hass.async_add_executor_job(
                        lambda: candidate.create(data, self.now(), **kwargs)
                    )
                elif operation == "update":
                    await self.hass.async_add_executor_job(
                        lambda: candidate.update(uid, data, self.now(), **kwargs)
                    )
                elif operation == "set_enabled":
                    candidate.set_enabled(uid, data["enabled"], self.now())
                elif operation == "delete":
                    await self.hass.async_add_executor_job(lambda: candidate.delete(uid, **kwargs))
                else:
                    raise ValueError("Unknown calendar operation.")
                encoded = await self.hass.async_add_executor_job(candidate.serialize)
                # Commit only after durable write succeeds; failed saves leave the old schedule intact.
                await self.store.async_save({"ics": encoded})
            except (ValueError, KeyError, TypeError) as err:
                raise HomeAssistantError(str(err)) from err
            self.model = candidate
            if operation != "create":
                await self.audio.release(self.token(uid))
                old_state = self.runtime["alarms"].get(uid, {})
                self.runtime["alarms"][uid] = {
                    key: value for key, value in old_state.items()
                    if key in ("handled", "last_missed", "last_fired")
                }
            if operation == "delete" and not any(e.uid == uid for e in candidate.roots()):
                self.runtime["alarms"].pop(uid, None)
            # Calendar storage is authoritative even if runtime storage becomes unavailable.
            try:
                await self._save_runtime()
            except Exception:
                _LOGGER.exception("Calendar saved, but occurrence history could not be saved")
            await self._refresh()
            self.emit(operation, uid)
            return {"uid": uid}

    async def action(self, action, uid, minutes=None):
        async with self.lock:
            if self.closed:
                raise HomeAssistantError("The alarm calendar is unloading. Retry shortly.")
            root = self.model.root(uid)
            old_runtime = copy.deepcopy(self.runtime)
            state = self.runtime["alarms"].setdefault(uid, {})
            if action == "snooze":
                if state.get("state") != "ringing":
                    raise HomeAssistantError("Only a ringing alarm can be snoozed.")
                definition = next(item for item in self.definitions if item["uid"] == uid)
                minutes = minutes if minutes is not None else definition["audio"].get(
                    "snooze_minutes", self.settings["snooze_minutes"]
                )
                if type(minutes) is not int or not 1 <= minutes <= 120:
                    raise HomeAssistantError("Snooze must be between 1 and 120 minutes.")
                now = self.now()
                snooze_until = datetime.fromtimestamp(now.timestamp() + minutes * 60, now.tzinfo)
                state.update(state="snoozed", snooze_until=snooze_until.isoformat())
            elif action == "dismiss":
                if not root.rrule:
                    candidate = await self.hass.async_add_executor_job(self.model.clone)
                    candidate.set_enabled(uid, False, self.now())
                    encoded = await self.hass.async_add_executor_job(candidate.serialize)
                    # Disable durably before stopping this one-time occurrence.
                    await self.store.async_save({"ics": encoded})
                    self.model = candidate
                state.update(state="dismissed")
                state.pop("snooze_until", None)
            else:
                raise HomeAssistantError("Unknown alarm action.")
            try:
                await self._save_runtime()
            except Exception:
                if action == "dismiss" and not root.rrule:
                    # The disabled calendar is authoritative even if the second
                    # store fails. Still stop audio and cancel pending callbacks.
                    _LOGGER.exception("Alarm disabled, but dismissal history could not be saved")
                else:
                    self.runtime = old_runtime
                    raise
            await self.audio.release(self.token(uid))
            await self._refresh()
            self.emit(action, uid)
            return {"uid": uid}

    def _clear_callbacks(self):
        for unsubscribe in self.callbacks.values():
            unsubscribe()
        self.callbacks.clear()

    def _schedule(self, key, when, function):
        @callback
        def execute(_):
            self.callbacks.pop(key, None)
            self.hass.async_create_task(function())
        self.callbacks[key] = async_track_point_in_utc_time(
            self.hass, execute, when.astimezone(timezone.utc)
        )

    async def _refresh(self):
        # A heartbeat can run at the same instant as an alarm callback. Preserve
        # due work before replacing the next-occurrence snapshot; _fire verifies
        # it against the committed calendar and the durable handled watermark.
        now = self.now()
        for previous in self.definitions:
            pending = previous.get("next_occurrence")
            if previous.get("enabled") and pending:
                when = datetime.fromisoformat(pending)
                if when.timestamp() <= now.timestamp():
                    self.hass.async_create_task(self._fire(previous["uid"], when))
            snooze = self.runtime["alarms"].get(previous["uid"], {}).get("snooze_until")
            if previous.get("enabled") and snooze:
                when = datetime.fromisoformat(snooze)
                if when.timestamp() <= now.timestamp():
                    self.hass.async_create_task(self._fire(previous["uid"], when, True))
        self._clear_callbacks()
        definitions = await self.hass.async_add_executor_job(self.model.definitions, now)
        for definition in definitions:
            uid = definition["uid"]
            state = self.runtime["alarms"].get(uid, {})
            definition.update({key: value for key, value in state.items() if key != "handled"})
            if not definition["enabled"]:
                definition["state"] = "disabled"
                continue
            pending = definition["next_occurrence"]
            if pending:
                when = datetime.fromisoformat(pending)
                if when.timestamp() > float(state.get("handled", 0)):
                    self._schedule((uid, "occurrence"), when,
                                   lambda u=uid, w=when: self._fire(u, w))
            elif definition["repeat"] == "once" and state.get("state") not in ("ringing", "snoozed"):
                definition.setdefault("state", "completed")
            snooze = state.get("snooze_until")
            if snooze:
                when = datetime.fromisoformat(snooze)
                if when.timestamp() > now.timestamp():
                    self._schedule((uid, "snooze"), when, lambda u=uid, w=when: self._fire(u, w, True))
            if state.get("state") == "ringing":
                until = datetime.fromisoformat(state["ring_until"])
                deadline = until if until.timestamp() > now.timestamp() else datetime.fromtimestamp(now.timestamp() + 1, now.tzinfo)
                self._schedule((uid, "timeout"), deadline,
                               lambda u=uid: self._timeout(u))
            definition.setdefault("state", "scheduled" if pending else "completed")
        self.definitions = definitions
        if self.calendar_entity:
            await self.calendar_entity.refresh()
        self.publish()

    async def _fire(self, uid, when, snooze=False):
        async with self.lock:
            if self.closed:
                return
            definition = next((item for item in self.definitions if item["uid"] == uid), None)
            if not definition or not definition["enabled"]:
                return
            state = self.runtime["alarms"].setdefault(uid, {})
            # Queued callbacks from an edited/disabled alarm must not fire.
            if snooze:
                if state.get("snooze_until") != when.isoformat():
                    return
            else:
                if when.timestamp() <= float(state.get("handled", 0)):
                    return
                actual = await self.hass.async_add_executor_job(
                    lambda: self.model.occurrences(when - timedelta(seconds=1), when + timedelta(seconds=1), enabled_only=True)
                )
                if not any(event.uid == uid and instant.timestamp() == when.timestamp() for instant, event in actual):
                    return
            old_runtime = copy.deepcopy(self.runtime)
            settings = self.settings | definition["audio"]
            now = self.now()
            ring_until = datetime.fromtimestamp(now.timestamp() + settings["ring_minutes"] * 60, now.tzinfo)
            state.update(state="ringing", last_fired=when.isoformat(), ring_started=now.isoformat(),
                         ring_until=ring_until.isoformat())
            if not snooze:
                state["handled"] = when.timestamp()
            state.pop("snooze_until", None)
            state.pop("audio_error", None)
            try:
                await self._save_runtime()
            except Exception as err:
                self.runtime = old_runtime
                self.runtime["alarms"].setdefault(uid, {})["audio_error"] = f"Occurrence could not be saved: {err}"
                await self._refresh()
                return
            @callback
            def on_error(message):
                state["audio_error"] = message
                for item in self.definitions:
                    if item["uid"] == uid:
                        item["audio_error"] = message
                self.publish()
                self.emit("audio_error", uid, error=message)
            await self.audio.release(self.token(uid))
            if not settings["media_players"]:
                on_error("No media players configured. Lifecycle events are still emitted.")
            else:
                await self.audio.acquire(self.token(uid), settings["media_players"], settings["sound"], on_error)
            await self._refresh()
            self.emit("fired", uid, occurrence=when.isoformat(), snoozed=snooze)

    async def _timeout(self, uid):
        async with self.lock:
            state = self.runtime["alarms"].get(uid, {})
            if state.get("state") != "ringing" or self.closed:
                return
            state["state"] = "timed_out"
            await self.audio.release(self.token(uid))
            await self._save_runtime()
            await self._refresh()
            self.emit("timed_out", uid)

    @callback
    def emit(self, action, uid, **extra):
        self.hass.bus.async_fire(EVENT, {"action": action, "entity_id": self.entity_id, "uid": uid, **extra})

    @callback
    def publish(self):
        for listener in list(self.listeners):
            listener()

    @callback
    def subscribe(self, listener):
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    def snapshot(self):
        return {"entity_id": self.entity_id, "time_zone": self.hass.config.time_zone,
                "defaults": self.settings, "alarms": self.definitions}
