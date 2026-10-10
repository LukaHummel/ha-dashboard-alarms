from types import SimpleNamespace

import pytest

from conftest import module


class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


class Selector:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        return value


module("homeassistant.config_entries", ConfigFlow=Flow, OptionsFlow=Flow)
module("homeassistant.helpers.selector", EntitySelector=Selector, EntitySelectorConfig=lambda **kwargs: kwargs)

from custom_components.dashboard_alarms.config_flow import (  # noqa: E402
    DashboardAlarmsConfigFlow, AlarmOptionsFlow,
)


@pytest.mark.asyncio
async def test_setup_and_options_flow_validation():
    flow = DashboardAlarmsConfigFlow()
    form = await flow.async_step_user()
    values = form["data_schema"]({"name": "Bedroom", "sound": "/dashboard_alarms/chime.wav", "snooze_minutes": 10, "ring_minutes": 10})
    result = await flow.async_step_user(values)
    assert result["type"] == "create_entry"
    assert result["data"]["media_players"] == []
    invalid = await flow.async_step_user(values | {"sound": "invalid"})
    assert invalid["errors"]["base"] == "invalid_settings"
    options = AlarmOptionsFlow()
    options.config_entry = SimpleNamespace(data=values, options={"ring_minutes": 5})
    form = await options.async_step_init()
    assert form["data_schema"]({})["ring_minutes"] == 5
