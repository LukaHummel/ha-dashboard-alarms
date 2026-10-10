"""Dashboard Alarms integration."""

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform

from .api import register
from .audio import AudioHub
from .const import CARD_URL, DOMAIN, STATIC_URL
from .manager import AlarmManager

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {"managers": {}, "audio": AudioHub(hass)})
    register(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)
    ])
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace and lovelace.resource_mode == "storage":
        resources = lovelace.resources
        try:
            await resources.async_get_info()
            existing = next((item for item in resources.async_items()
                             if item["url"].split("?")[0] == CARD_URL.split("?")[0]), None)
            if existing:
                await resources.async_update_item(existing["id"], {"url": CARD_URL, "res_type": "module"})
            else:
                await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
        except Exception:
            _LOGGER.exception("Add the dashboard card resource manually: %s", CARD_URL)
    return True


async def async_setup_entry(hass, entry):
    manager = AlarmManager(hass, entry, hass.data[DOMAIN]["audio"])
    await manager.load()
    entry.runtime_data = manager
    hass.data[DOMAIN]["managers"][entry.entry_id] = manager
    try:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CALENDAR])
    except Exception:
        await manager.close()
        hass.data[DOMAIN]["managers"].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    async def shutdown(_):
        await manager.close()
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown))
    return True


async def async_update_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    manager = entry.runtime_data
    if await hass.config_entries.async_unload_platforms(entry, [Platform.CALENDAR]):
        await manager.close()
        hass.data[DOMAIN]["managers"].pop(entry.entry_id, None)
        return True
    return False


async def async_remove_entry(hass, entry):
    # Explicit integration removal deletes its stores; reloading/unloading does not.
    from homeassistant.helpers.storage import Store
    for suffix in ("calendar", "runtime"):
        await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.{suffix}").async_remove()

