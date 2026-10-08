"""Tests for the SunGrow Modbus binary sensor entities."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest

PREFIX = "binary_sensor.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "state"),
    [
        # The seeded power flow status is 0x1B.
        ("pv_generating", STATE_ON),
        ("battery_charging", STATE_ON),
        ("battery_discharging", STATE_OFF),
        ("exporting_to_grid", STATE_ON),
        ("importing_from_grid", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_flow_bits(hass: HomeAssistant, key: str, state: str) -> None:
    """Test each power flow bit becomes its own binary sensor."""
    assert hass.states.get(f"{PREFIX}_{key}").state == state
