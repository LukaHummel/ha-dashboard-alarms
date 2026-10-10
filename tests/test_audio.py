"""Playback timing checks without wall-clock sleeps or real speakers."""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.dashboard_alarms import audio


@pytest.mark.asyncio
async def test_bundled_chime_restarts_after_three_seconds(hass, monkeypatch):
    hub = audio.AudioHub(hass)
    hub.owners["media_player.kitchen"] = {"one": (audio.DEFAULT_SOUND, lambda _: None)}
    delays = []

    async def sleep(seconds):
        delays.append(seconds)
        if len(delays) == 2:
            hub.owners.clear()

    monkeypatch.setattr(audio.asyncio, "sleep", sleep)
    await hub._loop("media_player.kitchen")
    assert delays == [3, 3]
    assert [name for _, name, _ in hass.service_calls] == ["play_media", "play_media"]


@pytest.mark.asyncio
async def test_custom_clip_uses_reported_duration_instead_of_fifteen_seconds(hass, monkeypatch):
    hub = audio.AudioHub(hass)
    hub.owners["media_player.kitchen"] = {"one": ("/long.mp3", lambda _: None)}
    hass.states.get = lambda _: SimpleNamespace(state="playing", attributes={"media_duration": 23})
    delays = []

    async def sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(audio.asyncio, "sleep", sleep)
    await hub._wait_for_sound("media_player.kitchen", "/long.mp3")
    assert sum(delays) == 23


@pytest.mark.asyncio
async def test_custom_clip_replays_on_player_completion(hass, monkeypatch):
    hub = audio.AudioHub(hass)
    hub.owners["media_player.kitchen"] = {"one": ("/short.mp3", lambda _: None)}
    states = iter(["playing", "playing", "idle"])
    hass.states.get = lambda _: SimpleNamespace(state=next(states), attributes={})
    delays = []

    async def sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(audio.asyncio, "sleep", sleep)
    await hub._wait_for_sound("media_player.kitchen", "/short.mp3")
    assert sum(delays) == 2


@pytest.mark.asyncio
async def test_custom_clip_can_be_cancelled_or_replaced_by_shared_owner(hass, monkeypatch):
    hub = audio.AudioHub(hass)
    hub.owners["media_player.kitchen"] = {"one": ("/long.mp3", lambda _: None)}

    async def replace(seconds):
        hub.owners["media_player.kitchen"]["two"] = ("/new.mp3", lambda _: None)

    monkeypatch.setattr(audio.asyncio, "sleep", replace)
    await hub._wait_for_sound("media_player.kitchen", "/long.mp3")

    async def cancel(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(audio.asyncio, "sleep", cancel)
    with pytest.raises(asyncio.CancelledError):
        await hub._wait_for_sound("media_player.kitchen", audio.DEFAULT_SOUND)
