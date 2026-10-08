"""Tests that every translation says the same things as the English one."""

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component
import pytest

from custom_components.sungrow_modbus.const import DOMAIN

TRANSLATIONS = (
    Path(__file__).parent.parent
    / "custom_components"
    / "sungrow_modbus"
    / "translations"
)


def _strings(tree: dict[str, Any], path: str = "") -> Iterator[tuple[str, str]]:
    """Yield every string in a translation file by its dotted path."""
    for key, value in tree.items():
        if isinstance(value, dict):
            yield from _strings(value, f"{path}{key}.")
        else:
            yield f"{path}{key}", value


def _load(language: str) -> dict[str, str]:
    return dict(_strings(json.loads((TRANSLATIONS / f"{language}.json").read_text())))


@pytest.mark.parametrize(
    "language",
    [path.stem for path in TRANSLATIONS.glob("*.json") if path.stem != "en"],
)
def test_translation_matches_english(language: str) -> None:
    """Test a translation has every English string, and the same placeholders."""
    english = _load("en")
    translation = _load(language)

    assert translation.keys() == english.keys()
    for path, text in english.items():
        assert set(re.findall(r"{\w+}", translation[path])) == set(
            re.findall(r"{\w+}", text)
        ), path


async def test_swedish_loads_in_home_assistant(hass: HomeAssistant) -> None:
    """Test Home Assistant serves the Swedish names."""
    await async_setup_component(hass, "homeassistant", {})

    translations = await async_get_translations(hass, "sv", "entity", {DOMAIN})

    assert (
        translations[
            f"component.{DOMAIN}.entity.select.ems_mode.state.self_consumption"
        ]
        == "Egenförbrukning"
    )
