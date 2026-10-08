"""Actions of the SunGrow Modbus integration."""

from datetime import timedelta

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
import probatio

from .const import (
    ATTR_DURATION,
    ATTR_MODE,
    ATTR_POWER,
    DOMAIN,
    MAX_FORCE_DURATION,
    SERVICE_FORCE_BATTERY,
)
from .coordinator import SungrowModbusConfigEntry
from .select import FORCE_MODES

FORCE_BATTERY_SCHEMA = probatio.Schema(
    {
        # Optional with one inverter set up.
        probatio.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(ATTR_MODE): probatio.In(list(FORCE_MODES)),
        probatio.Required(ATTR_DURATION): probatio.All(
            cv.time_period,
            probatio.Range(min=timedelta(minutes=1), max=MAX_FORCE_DURATION),
        ),
        probatio.Optional(ATTR_POWER): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0)
        ),
    }
)


async def _async_force_battery(call: ServiceCall) -> None:
    entry: SungrowModbusConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY_ID)
    )
    if (operating_mode := entry.runtime_data.operating_mode) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_operating_mode"
        )
    await operating_mode.async_force(
        call.data[ATTR_MODE], call.data[ATTR_DURATION], call.data.get(ATTR_POWER)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_BATTERY,
        _async_force_battery,
        schema=FORCE_BATTERY_SCHEMA,
    )
