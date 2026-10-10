"""Authenticated alarm services and websocket API."""

import probatio as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

OPERATIONS = {"create_alarm": "create", "update_alarm": "update", "set_enabled": "set_enabled", "delete_alarm": "delete"}
COMMANDS = [*OPERATIONS, "snooze", "dismiss"]


def get_manager(hass, entity_id):
    for manager in hass.data[DOMAIN]["managers"].values():
        if manager.entity_id == entity_id:
            return manager
    raise HomeAssistantError("Select a Dashboard Alarms calendar entity.")


async def check_permission(hass, user_id, entity_id, policy):
    if user_id is None:
        return  # Internal automation/service calls.
    user = await hass.auth.async_get_user(user_id)
    if user is None or not user.permissions.check_entity(entity_id, policy):
        raise Unauthorized(entity_id=entity_id)


async def dispatch(manager, command, data):
    uid = data.get("uid")
    if command != "create_alarm" and not uid:
        raise HomeAssistantError("An alarm UID is required.")
    if command in ("snooze", "dismiss"):
        return await manager.action(command, uid, data.get("minutes"))
    if command not in OPERATIONS:
        raise HomeAssistantError("Unknown alarm command.")
    return await manager.mutate(OPERATIONS[command], uid, data.get("alarm", data))


def check_audio_permissions(user, data):
    """A calendar-control permission must not grant arbitrary speaker control."""
    alarm = data.get("alarm", data)
    audio = alarm.get("audio", {}) if isinstance(alarm, dict) else {}
    if not isinstance(audio, dict):
        raise HomeAssistantError("Audio settings must be an object.")
    for target in audio.get("media_players", []) or []:
        if not user.permissions.check_entity(target, POLICY_CONTROL):
            raise Unauthorized(entity_id=target)


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/list",
    vol.Required("entity_id"): cv.entity_id,
})
@websocket_api.async_response
async def ws_list(hass, connection, msg):
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_READ):
        raise Unauthorized(entity_id=msg["entity_id"])
    try:
        snapshot = get_manager(hass, msg["entity_id"]).snapshot()
        snapshot["can_control"] = connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL)
        connection.send_result(msg["id"], snapshot)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "alarm_error", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/command",
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("command"): vol.In(COMMANDS),
    vol.Optional("uid"): str,
    vol.Optional("alarm"): dict,
    vol.Optional("minutes"): int,
})
@websocket_api.async_response
async def ws_command(hass, connection, msg):
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])
    check_audio_permissions(connection.user, msg)
    try:
        result = await dispatch(get_manager(hass, msg["entity_id"]), msg["command"], msg)
        connection.send_result(msg["id"], result)
    except Exception as err:
        connection.send_error(msg["id"], "alarm_error", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/subscribe",
    vol.Required("entity_id"): cv.entity_id,
})
@websocket_api.async_response
async def ws_subscribe(hass, connection, msg):
    entity_id = msg["entity_id"]
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)
    try:
        manager = get_manager(hass, entity_id)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "alarm_error", str(err))
        return
    @callback
    def send():
        if connection.user.permissions.check_entity(entity_id, POLICY_READ):
            snapshot = manager.snapshot()
            snapshot["can_control"] = connection.user.permissions.check_entity(entity_id, POLICY_CONTROL)
            connection.send_message(websocket_api.event_message(msg["id"], snapshot))
    connection.subscriptions[msg["id"]] = manager.subscribe(send)
    connection.send_result(msg["id"])
    send()


def register(hass):
    for function in (ws_list, ws_command, ws_subscribe):
        websocket_api.async_register_command(hass, function)
    for command in COMMANDS:
        async def handle(call, selected=command):
            data = dict(call.data)
            await check_permission(hass, call.context.user_id, data["entity_id"], POLICY_CONTROL)
            if call.context.user_id:
                check_audio_permissions(await hass.auth.async_get_user(call.context.user_id), data)
            try:
                return await dispatch(get_manager(hass, data["entity_id"]), selected, data)
            except (ValueError, KeyError, TypeError) as err:
                raise HomeAssistantError(str(err)) from err
        hass.services.async_register(DOMAIN, command, handle,
            schema=vol.Schema({vol.Required("entity_id"): cv.entity_id,
                               vol.Optional("uid"): str, vol.Optional("alarm"): dict,
                               vol.Optional("minutes"): int}, extra=vol.ALLOW_EXTRA),
            supports_response=SupportsResponse.OPTIONAL)

