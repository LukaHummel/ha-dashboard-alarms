"""Frontend registration must not depend on a Lovelace card being mounted."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace
import sys
import types

import pytest

from custom_components.dashboard_alarms.const import NOTIFICATIONS_URL, STATIC_URL
# Reuse the API adapters so this setup test also runs on its own.
from test_api import register


@pytest.mark.asyncio
async def test_setup_registers_global_module_without_lovelace_resources(hass, monkeypatch):
    urls = []
    static_paths = []

    def adapter(name, **values):
        module = types.ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)

    adapter("homeassistant.components.frontend", add_extra_js_url=lambda _, url: urls.append(url))
    adapter("homeassistant.components.http", StaticPathConfig=lambda *args: args)
    adapter("homeassistant.components.lovelace.const", LOVELACE_DATA="lovelace")
    monkeypatch.setattr(sys.modules["homeassistant.const"], "EVENT_HOMEASSISTANT_STOP", "stop", raising=False)
    monkeypatch.setattr(sys.modules["homeassistant.const"], "Platform", SimpleNamespace(CALENDAR="calendar"), raising=False)
    path = Path(__file__).resolve().parents[1] / "custom_components/dashboard_alarms/__init__.py"
    loader = SourceFileLoader("custom_components.dashboard_alarms.setup_adapter", str(path))
    # Load the actual integration entry point with normal relative imports.
    module = module_from_spec(spec_from_loader(loader.name, loader, is_package=False))
    loader.exec_module(module)
    assert module.register is register
    monkeypatch.setattr(module, "register", lambda _: None)

    async def register_paths(paths):
        static_paths.extend(paths)

    hass.data = {}
    hass.http = SimpleNamespace(async_register_static_paths=register_paths)
    assert await module.async_setup(hass, {})
    assert urls == [NOTIFICATIONS_URL]
    assert static_paths[0][0] == STATIC_URL
    assert "managers" in hass.data["dashboard_alarms"]
