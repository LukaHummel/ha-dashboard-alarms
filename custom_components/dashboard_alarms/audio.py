"""Shared media-player ownership across all alarm calendars."""

import asyncio
import logging
import mimetypes
from urllib.parse import urlsplit

from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.components.media_source import async_resolve_media
from homeassistant.helpers.network import get_url

from .const import DEFAULT_SOUND

_LOGGER = logging.getLogger(__name__)
DEFAULT_SOUND_SECONDS = 3
UNKNOWN_SOUND_SECONDS = 15


class AudioHub:
    """One repeat loop per player; releasing one owner cannot silence another."""

    def __init__(self, hass):
        self.hass = hass
        self.owners = {}
        self.tasks = {}
        self.lock = asyncio.Lock()

    async def acquire(self, token, targets, sound, on_error):
        async with self.lock:
            for target in targets:
                owners = self.owners.setdefault(target, {})
                owners[token] = (sound, on_error)
                if target not in self.tasks:
                    self.tasks[target] = self.hass.async_create_background_task(
                        self._loop(target), f"Dashboard alarm audio: {target}"
                    )

    async def _loop(self, target):
        while target in self.owners:
            # Most recently ringing alarm supplies the sound for shared targets.
            owners = list(self.owners[target].values())
            sound = owners[-1][0]
            try:
                state = self.hass.states.get(target)
                if state is None or state.state in ("unknown", "unavailable"):
                    raise ValueError(f"{target} is unavailable")
                if sound.startswith("media-source://"):
                    media = await async_resolve_media(self.hass, sound, target)
                    url, media_type = async_process_play_media_url(self.hass, media.url), media.mime_type
                else:
                    if sound.startswith("/dashboard_alarms/"):
                        url = get_url(self.hass, prefer_external=False) + sound
                    else:
                        url = async_process_play_media_url(self.hass, sound)
                    media_type = mimetypes.guess_type(urlsplit(sound).path)[0] or "music"
                await asyncio.wait_for(self.hass.services.async_call(
                    "media_player", "play_media",
                    {"entity_id": target, "media_content_id": url, "media_content_type": media_type},
                    blocking=True,
                ), timeout=12)
                await self._wait_for_sound(target, sound)
            except Exception as err:  # Device integrations may raise arbitrary errors.
                _LOGGER.warning("Alarm playback failed on %s: %s", target, err)
                for _, on_error in owners:
                    on_error(f"{target}: {err}")
                await asyncio.sleep(5)

    async def _wait_for_sound(self, target, sound):
        """Replay when the clip finishes, without restarting long audio early."""
        if sound.split("?", 1)[0] == DEFAULT_SOUND:
            await asyncio.sleep(DEFAULT_SOUND_SECONDS)
            return
        # Give the player a chance to publish the newly loaded clip's metadata.
        await asyncio.sleep(1)
        elapsed = 1.0
        playing = False
        duration = None
        while target in self.owners:
            # A new/shared owner may have supplied a different sound.
            if list(self.owners[target].values())[-1][0] != sound:
                return
            state = self.hass.states.get(target)
            if state is None or state.state in ("unknown", "unavailable"):
                return
            if state.state == "playing":
                playing = True
            elif playing and state.state in ("idle", "off", "paused"):
                return
            reported = getattr(state, "attributes", {}).get("media_duration")
            if isinstance(reported, (int, float)) and 0 < reported < 86400:
                duration = reported
            if elapsed >= (duration or UNKNOWN_SOUND_SECONDS):
                return
            delay = min(0.5, (duration or UNKNOWN_SOUND_SECONDS) - elapsed)
            await asyncio.sleep(delay)
            elapsed += delay

    async def release(self, token):
        stops = []
        async with self.lock:
            for target, owners in list(self.owners.items()):
                if token not in owners:
                    continue
                del owners[token]
                if owners:
                    continue
                del self.owners[target]
                task = self.tasks.pop(target, None)
                if task:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                stops.append(target)
            # Serialize stop with acquire, so a new alarm cannot be stopped by an old release.
            for target in stops:
                try:
                    await asyncio.wait_for(self.hass.services.async_call(
                        "media_player", "media_stop", {"entity_id": target}, blocking=True,
                    ), timeout=12)
                except Exception as err:
                    _LOGGER.warning("Could not stop alarm audio on %s: %s", target, err)

