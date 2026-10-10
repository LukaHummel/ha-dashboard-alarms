"""API schema and permission tests using real probatio validation."""

import copy
from enum import Enum
import sys
from types import SimpleNamespace

import probatio
import pytest

from conftest import HomeAssistantError, module


class Unauthorized(HomeAssistantError):
    def __init__(self, entity_id):
        self.entity_id = entity_id


class SupportsResponse(Enum):
    OPTIONAL = "optional"


def websocket_command(schema):
    def decorate(function):
        function.schema = probatio.Schema(schema)
        return function
    return decorate


sys.modules["homeassistant.core"].SupportsResponse = SupportsResponse
sys.modules["homeassistant.exceptions"].Unauthorized = Unauthorized
module("homeassistant.auth")
module("homeassistant.auth.permissions")
module("homeassistant.auth.permissions.const", POLICY_CONTROL="control", POLICY_READ="read")
module("homeassistant.helpers.config_validation", entity_id=str)
module("homeassistant.components.websocket_api", websocket_command=websocket_command,
       async_response=lambda function: function, event_message=lambda identifier, data: {"id": identifier, "event": data},
       async_register_command=lambda hass, command: None)

from custom_components.dashboard_alarms.api import (  # noqa: E402
    check_permission, dispatch, register, ws_command, ws_list, ws_subscribe,
)


class Connection:
    def __init__(self, allowed):
        self.user = SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda entity_id, policy: (entity_id, policy) in allowed))
        self.subscriptions = {}
        self.messages = []

    def send_result(self, identifier, result=None):
        self.messages.append(("result", identifier, copy.deepcopy(result)))

    def send_error(self, identifier, code, message):
        self.messages.append(("error", identifier, message))

    def send_message(self, message):
        self.messages.append(("event", message))


class Manager:
    entity_id = "calendar.alarms"

    def __init__(self):
        self.calls = []
        self.listeners = set()

    def snapshot(self):
        return {"entity_id": self.entity_id, "alarms": [{"uid": "one", "enabled": False}]}

    async def mutate(self, operation, uid, data):
        self.calls.append((operation, uid, data))
        return {"uid": uid or "created"}

    async def action(self, operation, uid, minutes):
        self.calls.append((operation, uid, minutes))
        return {"uid": uid}

    def subscribe(self, callback):
        self.listeners.add(callback)
        return lambda: self.listeners.discard(callback)


def setup(hass):
    manager = Manager()
    hass.data = {"dashboard_alarms": {"managers": {"one": manager}}}
    return manager


@pytest.mark.asyncio
async def test_list_requires_calendar_read_permission(hass):
    setup(hass)
    msg = {"id": 1, "entity_id": "calendar.alarms"}
    with pytest.raises(Unauthorized):
        await ws_list(hass, Connection(set()), msg)
    connection = Connection({("calendar.alarms", "read")})
    await ws_list(hass, connection, msg)
    assert connection.messages[0][2]["alarms"][0]["enabled"] is False
    assert connection.messages[0][2]["can_control"] is False


@pytest.mark.asyncio
async def test_mutation_requires_calendar_and_override_target_permission(hass):
    manager = setup(hass)
    msg = {"id": 1, "entity_id": "calendar.alarms", "command": "create_alarm",
           "alarm": {"start": "2026-10-12T07:00:00", "audio": {"media_players": ["media_player.kitchen"]}}}
    with pytest.raises(Unauthorized):
        await ws_command(hass, Connection({("calendar.alarms", "read")}), msg)
    with pytest.raises(Unauthorized):
        await ws_command(hass, Connection({("calendar.alarms", "control")}), msg)
    assert not manager.calls
    connection = Connection({("calendar.alarms", "control"), ("media_player.kitchen", "control")})
    await ws_command(hass, connection, msg)
    assert manager.calls[0][0] == "create"


@pytest.mark.asyncio
async def test_live_subscription_rechecks_permission_and_unsubscribes(hass):
    manager = setup(hass)
    allowed = {("calendar.alarms", "read")}
    connection = Connection(allowed)
    await ws_subscribe(hass, connection, {"id": 4, "entity_id": "calendar.alarms"})
    assert len(connection.messages) == 2
    allowed.clear()
    next(iter(manager.listeners))()
    assert len(connection.messages) == 2
    connection.subscriptions[4]()
    assert not manager.listeners


@pytest.mark.asyncio
async def test_subscription_reports_current_control_permission(hass):
    manager = setup(hass)
    allowed = {("calendar.alarms", "read"), ("calendar.alarms", "control")}
    connection = Connection(allowed)
    await ws_subscribe(hass, connection, {"id": 4, "entity_id": "calendar.alarms"})
    assert connection.messages[-1][1]["event"]["can_control"] is True
    allowed.remove(("calendar.alarms", "control"))
    next(iter(manager.listeners))()
    assert connection.messages[-1][1]["event"]["can_control"] is False


@pytest.mark.asyncio
async def test_service_user_permissions_and_internal_automation(hass):
    user = Connection(set()).user
    async def get_user(identifier):
        return user
    hass.auth = SimpleNamespace(async_get_user=get_user)
    with pytest.raises(Unauthorized):
        await check_permission(hass, "user", "calendar.alarms", "control")
    await check_permission(hass, None, "calendar.alarms", "control")


@pytest.mark.asyncio
async def test_dispatch_missing_uid_and_snooze(hass):
    manager = setup(hass)
    with pytest.raises(HomeAssistantError, match="UID"):
        await dispatch(manager, "dismiss", {})
    await dispatch(manager, "snooze", {"uid": "one", "minutes": 5})
    assert manager.calls[-1] == ("snooze", "one", 5)


def test_command_schema_rejects_unknown_command_and_bad_alarm_object():
    with pytest.raises(probatio.Invalid):
        ws_command.schema({"type": "dashboard_alarms/command", "entity_id": "calendar.alarms", "command": "oops"})
    with pytest.raises(probatio.Invalid):
        ws_command.schema({"type": "dashboard_alarms/command", "entity_id": "calendar.alarms", "command": "create_alarm", "alarm": "bad"})


def test_all_service_handlers_register_and_validate_schema(hass):
    registrations = {}
    hass.services.async_register = lambda domain, name, handler, **kwargs: registrations.update({name: (handler, kwargs)})
    register(hass)
    assert set(registrations) == {"create_alarm", "update_alarm", "set_enabled", "delete_alarm", "snooze", "dismiss"}
    for _, kwargs in registrations.values():
        assert kwargs["schema"]({"entity_id": "calendar.alarms"})["entity_id"] == "calendar.alarms"
