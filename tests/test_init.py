"""Test component setup."""
import json
from pathlib import Path

from homeassistant.setup import async_setup_component

from custom_components.kostal import __version__
from custom_components.kostal.const import DOMAIN


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


def test_version_matches_manifest():
    """The card cache-busting version must follow the manifest."""
    manifest = Path(__file__).parent.parent / "custom_components" / "kostal" / "manifest.json"
    assert json.loads(manifest.read_text())["version"] == __version__
