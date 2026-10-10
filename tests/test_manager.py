import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.dashboard_alarms.audio import AudioHub
from custom_components.dashboard_alarms.manager import AlarmManager

ZONE = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 10, 12, tzinfo=ZONE)


class Audio:
    def __init__(self):
        self.active = {}
        self.acquisitions = []

    async def acquire(self, token, targets, sound, on_error):
        self.active[token] = targets
        self.acquisitions.append(token)

    async def release(self, token):
        self.active.pop(token, None)


async def manager(hass, now=NOW, audio=None):
    entry = SimpleNamespace(entry_id="test", data={"media_players": ["media_player.kitchen"]}, options={})
    result = AlarmManager(hass, entry, audio or Audio())
    result.now = lambda: now
    await result.load()
    await result.start()
    return result


@pytest.mark.asyncio
async def test_fire_once_even_if_duplicate_callbacks_and_closed_dashboard(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00"}))["uid"]
    when = NOW + timedelta(minutes=1)
    m.now = lambda: when
    await m._fire(uid, when)
    await m._fire(uid, when)
    await hass.drain()
    assert len(m.audio.acquisitions) == 1
    assert m.definitions[0]["state"] == "ringing"
    assert [data["action"] for _, data in hass.events].count("fired") == 1
    await m.action("dismiss", uid)
    assert not m.audio.active
    await m.close()


@pytest.mark.asyncio
async def test_heartbeat_at_exact_alarm_time_does_not_drop_alarm(hass):
    m = await manager(hass)
    await m.mutate("create", data={"start": "2026-10-10T12:01:00", "repeat": "daily"})
    m.now = lambda: NOW + timedelta(minutes=1)
    await m._tick()
    for _ in range(8):
        await asyncio.sleep(0)
    assert len(m.audio.acquisitions) == 1
    assert m.definitions[0]["next_occurrence"].startswith("2026-10-11")
    await m.close()


@pytest.mark.asyncio
async def test_disable_keeps_alarm_cancels_audio_and_stale_callbacks(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00", "repeat": "daily"}))["uid"]
    when = NOW + timedelta(minutes=1)
    await m.mutate("set_enabled", uid, {"enabled": False})
    await m._fire(uid, when)
    assert not m.audio.active
    assert len(m.definitions) == 1 and m.definitions[0]["state"] == "disabled"
    await m.mutate("set_enabled", uid, {"enabled": True})
    m.now = lambda: when
    await m._fire(uid, when)
    assert m.audio.active
    await m.mutate("set_enabled", uid, {"enabled": False})
    assert not m.audio.active
    await m.close()


@pytest.mark.asyncio
async def test_failed_calendar_save_keeps_old_schedule(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-11T07:00:00"}))["uid"]
    before = m.model.serialize()
    m.store.fail = True
    with pytest.raises(OSError, match="disk full"):
        await m.mutate("delete", uid)
    assert m.model.serialize() == before
    assert m.definitions[0]["uid"] == uid
    await m.close()


@pytest.mark.asyncio
async def test_failed_runtime_save_does_not_play_sound(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00"}))["uid"]
    m.runtime_store.fail = True
    m.now = lambda: NOW + timedelta(minutes=1)
    await m._fire(uid, m.now())
    assert not m.audio.active
    await m.close()


@pytest.mark.asyncio
async def test_snooze_survives_restart_without_changing_calendar(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00", "repeat": "daily"}))["uid"]
    m.now = lambda: NOW + timedelta(minutes=1)
    await m._fire(uid, m.now())
    before = m.model.serialize()
    await m.action("snooze", uid)
    assert m.model.serialize() == before
    await m.close()
    restored = await manager(hass, NOW + timedelta(minutes=3))
    assert restored.definitions[0]["state"] == "snoozed"
    due = datetime.fromisoformat(restored.definitions[0]["snooze_until"])
    restored.now = lambda: due
    await restored._fire(uid, due, True)
    assert restored.audio.active
    assert restored.definitions[0]["next_occurrence"].startswith("2026-10-11")
    await restored.close()


@pytest.mark.asyncio
async def test_restart_marks_missed_without_ringing(hass):
    m = await manager(hass)
    await m.mutate("create", data={"start": "2026-10-10T12:01:00", "repeat": "daily"})
    await m.close()
    restored = await manager(hass, NOW + timedelta(minutes=3))
    assert not restored.audio.active
    assert restored.definitions[0]["last_missed"].startswith("2026-10-10T12:01")
    assert restored.definitions[0]["next_occurrence"].startswith("2026-10-11")
    await restored.close()


@pytest.mark.asyncio
async def test_extended_downtime_marks_one_time_alarm_missed(hass):
    m = await manager(hass)
    await m.mutate("create", data={"start": "2026-10-11T07:00:00"})
    await m.close()
    restored = await manager(hass, NOW + timedelta(days=60))
    assert restored.definitions[0]["last_missed"].startswith("2026-10-11T07:00")
    assert not restored.audio.active
    await restored.close()


@pytest.mark.asyncio
async def test_snooze_heartbeat_at_due_time(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00"}))["uid"]
    m.now = lambda: NOW + timedelta(minutes=1)
    await m._fire(uid, m.now())
    await m.action("snooze", uid)
    m.now = lambda: NOW + timedelta(minutes=11)
    await m._tick()
    for _ in range(8):
        await asyncio.sleep(0)
    assert len(m.audio.acquisitions) == 2
    await m.close()


@pytest.mark.asyncio
async def test_snooze_and_ring_limit_use_elapsed_minutes_across_dst(hass):
    now = datetime(2026, 10, 25, 2, 54, tzinfo=ZONE, fold=0)
    m = await manager(hass, now)
    uid = (await m.mutate("create", data={"start": "2026-10-25T02:55:00"}))["uid"]
    when = datetime(2026, 10, 25, 2, 55, tzinfo=ZONE, fold=0)
    m.now = lambda: when
    await m._fire(uid, when)
    state = m.runtime["alarms"][uid]
    assert datetime.fromisoformat(state["ring_until"]).timestamp() - when.timestamp() == 600
    await m.action("snooze", uid)
    assert datetime.fromisoformat(state["snooze_until"]).timestamp() - when.timestamp() == 600
    await m.close()


@pytest.mark.asyncio
async def test_timeout_cleanup(hass):
    m = await manager(hass)
    uid = (await m.mutate("create", data={"start": "2026-10-10T12:01:00"}))["uid"]
    m.now = lambda: NOW + timedelta(minutes=1)
    await m._fire(uid, m.now())
    await m._timeout(uid)
    assert not m.audio.active
    assert m.definitions[0]["state"] == "timed_out"
    await m.close()
    assert all(record["cancelled"] for record in hass.callbacks)


@pytest.mark.asyncio
async def test_audio_shared_target_and_unavailable_target(hass):
    hub = AudioHub(hass)
    errors = []
    await hub.acquire("one", ["media_player.kitchen"], "/chime.wav", errors.append)
    await hub.acquire("two", ["media_player.kitchen"], "/chime.wav", errors.append)
    await asyncio.sleep(0)
    assert len(hub.tasks) == 1
    await hub.release("one")
    assert not any(name == "media_stop" for _, name, _ in hass.service_calls)
    await hub.release("two")
    assert any(name == "media_stop" for _, name, _ in hass.service_calls)
    assert not hub.tasks
    hass.states.get = lambda _: SimpleNamespace(state="unavailable")
    await hub.acquire("three", ["media_player.missing"], "/chime.wav", errors.append)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert errors and "unavailable" in errors[-1]
    await hub.release("three")


@pytest.mark.asyncio
async def test_media_source_resolves_signed_absolute_url(hass, monkeypatch):
    from custom_components.dashboard_alarms import audio
    async def resolve(hass, uri, player):
        assert player == "media_player.kitchen"
        return SimpleNamespace(url="/media/local/alarm.wav", mime_type="audio/wav")
    monkeypatch.setattr(audio, "async_resolve_media", resolve)
    hub = AudioHub(hass)
    await hub.acquire("one", ["media_player.kitchen"], "media-source://media_source/local/alarm.wav", lambda _: None)
    for _ in range(3):
        await asyncio.sleep(0)
    assert hass.service_calls[0][2]["media_content_id"].startswith("http://homeassistant.local:8123/media/local/")
    assert "authSig=" in hass.service_calls[0][2]["media_content_id"]
    assert hass.service_calls[0][2]["media_content_type"] == "audio/wav"
    await hub.release("one")
