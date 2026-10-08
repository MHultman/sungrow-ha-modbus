"""Config flow to configure the SunGrow Modbus integration."""

from collections.abc import Mapping
from typing import Any, override

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import probatio

from .const import (
    CONF_BATTERY_MAX_POWER,
    CONF_CONNECTION,
    CONF_UNIT_ID,
    CONNECTION_LAN,
    CONNECTION_WINET,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .entity import inverter_name
from .helpers import apply_link_timing, create_modbus_params
from .inverter import SungrowConnectionError, SungrowError, SungrowInverter

SECTION_MORE_OPTIONS = "more_options"

STEP_USER = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_CONNECTION, default=CONNECTION_WINET): SelectSelector(
            SelectSelectorConfig(
                options=[CONNECTION_WINET, CONNECTION_LAN],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_CONNECTION,
            )
        ),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(int),
        ),
        # Almost every inverter answers on the factory-default device ID, so
        # that setting is tucked away in a collapsed section.
        probatio.Required(SECTION_MORE_OPTIONS): section(
            probatio.Schema(
                {
                    probatio.Required(
                        CONF_UNIT_ID, default=DEFAULT_UNIT_ID
                    ): probatio.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                        probatio.Coerce(int),
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the sectioned form input into config entry data."""
    data = dict(user_input)
    data[CONF_UNIT_ID] = data.pop(SECTION_MORE_OPTIONS)[CONF_UNIT_ID]
    # One connection is shared per host and port, so spelling matters.
    data[CONF_HOST] = data[CONF_HOST].strip().lower()
    return data


def _sectioned(data: Mapping[str, Any]) -> dict[str, Any]:
    """Shape config entry data back into the sectioned form input."""
    return {
        **{key: value for key, value in data.items() if key != CONF_UNIT_ID},
        SECTION_MORE_OPTIONS: {CONF_UNIT_ID: data[CONF_UNIT_ID]},
    }


STEP_OPTIONS = probatio.Schema(
    {
        # Left empty, the battery power controls go as high as the hardware is
        # rated for.
        probatio.Optional(CONF_BATTERY_MAX_POWER): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=100,
                    max=50000,
                    step=100,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="W",
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


class SungrowModbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SunGrow Modbus config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SungrowModbusOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask how the inverter is reached, then probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _flatten(user_input)
            errors, inverter = await self._async_validate(data)
            if inverter is not None:
                await self.async_set_unique_id(inverter.identity.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=inverter_name(inverter.identity.model), data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of how the inverter is reached.

        The inverter may move to another address, but it must stay the same
        inverter: the probed serial number has to match the entry's unique ID.
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            data = _flatten(user_input)
            errors, inverter = await self._async_validate(data)
            if inverter is not None:
                await self.async_set_unique_id(inverter.identity.serial_number)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER, user_input or _sectioned(entry.data)
            ),
            errors=errors,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], SungrowInverter | None]:
        """Probe the inverter, returning form errors and the probed inverter."""
        try:
            async with async_get_temporary_unit(
                self.hass, create_modbus_params(data), data[CONF_UNIT_ID]
            ) as unit:
                apply_link_timing(unit, data[CONF_CONNECTION])
                inverter = await SungrowInverter.async_probe(unit)
        except HomeAssistantError, SungrowConnectionError:
            # HomeAssistantError: the device is already in use over different
            # link settings, which one connection cannot honour.
            return {"base": "cannot_connect"}, None
        except SungrowError:
            return {"base": "no_sungrow_inverter"}, None

        return {}, inverter


class SungrowModbusOptionsFlow(OptionsFlowWithReload):
    """Handle the SunGrow Modbus options: the battery power cap."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the battery power cap; the entry reloads to apply it."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_OPTIONS, self.config_entry.options
            ),
        )
