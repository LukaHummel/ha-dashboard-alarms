"""User and options flows."""

import probatio as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN
from .model import validate_options


def schema(values):
    return vol.Schema({
        vol.Required("name", default=values["name"]): str,
        vol.Optional("media_players", default=values["media_players"]): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=True)),
        vol.Required("sound", default=values["sound"]): str,
        vol.Required("snooze_minutes", default=values["snooze_minutes"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        vol.Required("ring_minutes", default=values["ring_minutes"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
    })


class DashboardAlarmsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                validate_options(user_input)
                if not user_input["name"].strip():
                    raise ValueError("Name is empty")
                return self.async_create_entry(title=user_input["name"], data=user_input)
            except ValueError:
                errors["base"] = "invalid_settings"
        return self.async_show_form(step_id="user", data_schema=schema(DEFAULTS | (user_input or {})), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AlarmOptionsFlow()


class AlarmOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                validate_options(user_input)
                if not user_input["name"].strip():
                    raise ValueError("Name is empty")
                return self.async_create_entry(title="", data=user_input)
            except ValueError:
                errors["base"] = "invalid_settings"
        values = DEFAULTS | self.config_entry.data | self.config_entry.options | (user_input or {})
        return self.async_show_form(step_id="init", data_schema=schema(values), errors=errors)

