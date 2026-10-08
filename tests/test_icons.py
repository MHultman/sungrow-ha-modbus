"""Tests that the icons belong to entities and states that exist."""

import json
from pathlib import Path

from PIL import Image
import pytest

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "sungrow_modbus"
ICONS = json.loads((INTEGRATION / "icons.json").read_text())
ENTITIES = json.loads((INTEGRATION / "translations" / "en.json").read_text())["entity"]

STATE_ICONS = [
    (platform, key, icon)
    for platform, entities in ICONS["entity"].items()
    for key, icon in entities.items()
]


@pytest.mark.parametrize(("platform", "key", "icon"), STATE_ICONS)
def test_icon_belongs_to_an_entity(platform: str, key: str, icon: dict) -> None:
    """Test an icon names an entity, and states that entity has."""
    assert key in ENTITIES[platform]
    states = set(icon.get("state", {}))
    if platform in ("binary_sensor", "switch"):
        assert states <= {"on", "off"}
    else:
        assert states <= set(ENTITIES[platform][key].get("state", {}))


def test_preset_select_states_all_have_icons() -> None:
    """Test every option of the preset selects shows its own icon."""
    for key in ("operating_mode", "export_mode"):
        assert set(ICONS["entity"]["select"][key]["state"]) == set(
            ENTITIES["select"][key]["state"]
        )


def test_actions_have_icons() -> None:
    """Test every action in services.yaml has an icon."""
    services = (INTEGRATION / "services.yaml").read_text()
    names = [line[:-1] for line in services.splitlines() if line and line[0] != " "]
    assert set(names) == set(ICONS["services"])


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("icon.png", 256),
        ("icon@2x.png", 512),
        ("dark_icon.png", 256),
        ("dark_icon@2x.png", 512),
    ],
)
def test_brand_images(name: str, size: int) -> None:
    """Test the brand images Home Assistant shows are square, transparent PNGs."""
    with Image.open(INTEGRATION / "brand" / name) as image:
        assert image.format == "PNG"
        assert image.size == (size, size)
        assert image.mode == "RGBA"
