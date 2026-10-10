"""Small HA adapter fakes; calendar parsing/expansion uses the real ical library.

These tests do not claim to load a full Home Assistant instance.
"""

import asyncio
import copy
from datetime import datetime
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "work/alarm-libs").exists():
    sys.path.insert(0, str(ROOT / "work/alarm-libs"))
package = types.ModuleType("custom_components.dashboard_alarms")
package.__path__ = [str(ROOT / "custom_components/dashboard_alarms")]
sys.modules[package.__name__] = package


def module(name, **values):
    result = types.ModuleType(name)
    result.__dict__.update(values)
    sys.modules[name] = result
    return result


class HomeAssistantError(Exception):
    pass


class FakeStore:
    def __init__(self, hass, version, key):
        self.hass, self.key = hass, key
        self.fail = False

    async def async_load(self):
        return copy.deepcopy(self.hass.storage.get(self.key))

    async def async_save(self, data):
        if self.fail:
            raise OSError("disk full")
        self.hass.storage[self.key] = copy.deepcopy(data)


def track(hass, callback, when):
    record = {"callback": callback, "when": when, "cancelled": False}
    hass.callbacks.append(record)
    return lambda: record.update(cancelled=True)


class FakeHass:
    def __init__(self):
        self.storage = {}
        self.callbacks = []
        self.tasks = []
        self.events = []
        self.service_calls = []
        self.config = types.SimpleNamespace(time_zone="Europe/Berlin")
        self.bus = types.SimpleNamespace(async_fire=lambda name, data: self.events.append((name, data)),
                                         async_listen=lambda name, listener: lambda: None)
        self.states = types.SimpleNamespace(get=lambda _: types.SimpleNamespace(state="idle"))
        self.services = types.SimpleNamespace(async_call=self.service)

    async def service(self, domain, name, data, blocking):
        self.service_calls.append((domain, name, data))

    async def async_add_executor_job(self, function, *args):
        return function(*args)

    def async_create_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    def async_create_background_task(self, coroutine, name):
        return self.async_create_task(coroutine)

    async def drain(self):
        # Drain short-lived manager tasks, not persistent audio loops.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        finished = [task for task in self.tasks if task.done()]
        for task in finished:
            task.result()


for name in ("homeassistant", "homeassistant.helpers", "homeassistant.util", "homeassistant.components"):
    module(name)
module("homeassistant.core", callback=lambda func: func)
module("homeassistant.const", EVENT_CORE_CONFIG_UPDATE="core_config_updated")
module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
module("homeassistant.helpers.storage", Store=FakeStore)
module("homeassistant.helpers.event", async_track_point_in_utc_time=track,
       async_track_time_interval=lambda hass, callback, interval: lambda: None)
module("homeassistant.util.dt", now=datetime.now)
module("homeassistant.helpers.network", get_url=lambda *args, **kwargs: "http://homeassistant.local:8123")
module("homeassistant.components.media_source", async_resolve_media=None)
module("homeassistant.components.media_player", async_process_play_media_url=lambda hass, url:
       "http://homeassistant.local:8123" + url + "?authSig=test" if url.startswith("/") else url)


@pytest.fixture
def hass():
    return FakeHass()

