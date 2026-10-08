"""Support for SunGrow Modbus sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import registers as reg
from .const import LOGGER
from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .inverter import SungrowInverter
from .models import InverterModel
from .registers import Register

PARALLEL_UPDATES = 0

# What the running state register reports, by code. Several codes mean the same
# thing: Sungrow renumbered the states between protocol versions.
RUNNING_STATES: dict[int, str] = {
    0x0000: "running",
    0x0001: "stop",
    0x0002: "key_stop",
    0x0004: "emergency_stop",
    0x0008: "standby",
    0x0010: "initial_standby",
    0x0014: "microgrid",
    0x0020: "starting",
    0x0040: "running",
    0x0041: "off_grid_charge",
    0x0080: "derating",
    0x0100: "fault",
    0x0200: "update_failed",
    0x0400: "maintenance",
    0x0800: "forced_mode",
    0x1000: "off_grid",
    0x1111: "uninitialized",
    0x1200: "initial_standby",
    0x1300: "key_stop",
    0x1400: "standby",
    0x1500: "emergency_stop",
    0x1600: "starting",
    0x1700: "afci_self_test_shutdown",
    0x1800: "intelligent_station_building",
    0x1900: "safe_mode",
    0x2000: "open_loop",
    0x2500: "communication_fault",
    0x2501: "restarting",
    0x4000: "external_ems",
    0x4001: "emergency_charging",
    0x5500: "fault",
    0x8000: "stop",
    0x8100: "derating",
    0x8200: "dispatch",
    0x9100: "warning",
}


@dataclass(frozen=True, kw_only=True)
class SungrowModbusSensorEntityDescription(
    SensorEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus sensor entity."""

    value_fn: Callable[[SungrowInverter], StateType]
    # A lifetime counter that only ever grows, so a lower reading is a glitch.
    lifetime: bool = False


def _three_phase(model: InverterModel) -> bool:
    return model.three_phase


def _known(model: InverterModel) -> bool:
    """Return whether the model's settings are read, which unknown ones' are not."""
    return model.known


def _mppt(count: int) -> Callable[[InverterModel], bool]:
    return lambda model: model.mppt_count >= count


def _register(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    """Describe a sensor that shows one register as it is."""
    return SungrowModbusSensorEntityDescription(
        key=key,
        translation_key=key,
        blocks=(register.block,),
        value_fn=lambda inverter: inverter.value(register),
        **kwargs,
    )


def _power(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    return _register(
        key,
        register,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


def _voltage(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    return _register(
        key,
        register,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        **kwargs,
    )


def _current(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    return _register(
        key,
        register,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


def _temperature(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    return _register(
        key,
        register,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        **kwargs,
    )


def _energy(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusSensorEntityDescription:
    """Describe an energy counter: one for today, or one for all time.

    Today's counters reset at midnight, which a total_increasing sensor takes
    for a new cycle. The lifetime ones never go down.
    """
    return _register(
        key,
        register,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        lifetime=key.startswith("total_"),
        **kwargs,
    )


def _product(
    first: Register, second: Register
) -> Callable[[SungrowInverter], int | None]:
    """Return the power two registers measure, as voltage times current."""

    def value(inverter: SungrowInverter) -> int | None:
        voltage = inverter.value(first)
        current = inverter.value(second)
        if not isinstance(voltage, (int, float)) or not isinstance(
            current, (int, float)
        ):
            return None
        return round(voltage * current)

    return value


def _computed_power(
    key: str,
    value_fn: Callable[[SungrowInverter], int | None],
    *registers: Register,
    **kwargs: Any,
) -> SungrowModbusSensorEntityDescription:
    """Describe a power the inverter does not report but its registers give."""
    return SungrowModbusSensorEntityDescription(
        key=key,
        translation_key=key,
        blocks=tuple(dict.fromkeys(register.block for register in registers)),
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        **kwargs,
    )


def _signed(register: Register, sign: int) -> Callable[[SungrowInverter], int | None]:
    """Return a register's value flipped by sign."""

    def value(inverter: SungrowInverter) -> int | None:
        raw = inverter.value(register)
        return sign * raw if isinstance(raw, int) else None

    return value


def _positive_part(
    register: Register, sign: int
) -> Callable[[SungrowInverter], int | None]:
    """Return the part of a signed power flowing one way, and zero otherwise."""
    signed = _signed(register, sign)

    def value(inverter: SungrowInverter) -> int | None:
        power = signed(inverter)
        return None if power is None else max(power, 0)

    return value


def _consumed(
    generation: Register,
    export: Register,
    grid_import: Register,
    charge: Register,
    discharge: Register,
) -> Callable[[SungrowInverter], float | None]:
    """Return the energy the house used: what came in minus what went out."""

    def value(inverter: SungrowInverter) -> float | None:
        values = _numbers(inverter, generation, export, grid_import, charge, discharge)
        if values is None:
            return None
        pv, exported, imported, charged, discharged = values
        return round(pv - exported + imported - charged + discharged, 1)

    return value


def _numbers(inverter: SungrowInverter, *registers: Register) -> list[float] | None:
    """Return several registers' values, or None unless all of them have one."""
    values = [inverter.value(register) for register in registers]
    numbers = [value for value in values if isinstance(value, (int, float))]
    return numbers if len(numbers) == len(values) else None


def _battery_level_nominal(inverter: SungrowInverter) -> float | None:
    """Return the charge as a share of the whole battery.

    The battery level the inverter reports runs from 0 % at the minimum SoC to
    100 % at the maximum. With limits of 15 % and 90 %, a reported 50 % is
    52.5 % of the whole battery.
    """
    values = _numbers(inverter, reg.MIN_SOC, reg.MAX_SOC, reg.BATTERY_LEVEL)
    if values is None:
        return None
    low, high, level = values
    return round(low + (high - low) * level / 100, 1)


def _battery_charge_nominal(inverter: SungrowInverter) -> float | None:
    """Return the energy stored in the whole battery."""
    capacity = inverter.value(reg.BATTERY_CAPACITY)
    if (level := _battery_level_nominal(inverter)) is None or not isinstance(
        capacity, (int, float)
    ):
        return None
    return round(capacity * level / 100, 2)


def _battery_charge(inverter: SungrowInverter) -> float | None:
    """Return the energy that can still be drawn before the minimum SoC."""
    values = _numbers(
        inverter, reg.BATTERY_CAPACITY, reg.MIN_SOC, reg.MAX_SOC, reg.BATTERY_LEVEL
    )
    if values is None:
        return None
    capacity, low, high, level = values
    return round(capacity * (high - low) / 100 * level / 100, 2)


def _battery_charge_health_rated(inverter: SungrowInverter) -> float | None:
    """Return the drawable energy, scaled down by the battery's wear."""
    health = inverter.value(reg.BATTERY_STATE_OF_HEALTH)
    if (charge := _battery_charge(inverter)) is None or not isinstance(
        health, (int, float)
    ):
        return None
    return round(charge * health / 100, 2)


def _battery_energy(
    key: str, value_fn: Callable[[SungrowInverter], float | None]
) -> SungrowModbusSensorEntityDescription:
    return SungrowModbusSensorEntityDescription(
        key=key,
        translation_key=key,
        blocks=(reg.SYSTEM, reg.METER_BMS, reg.SOC_LIMITS),
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        exists_fn=_known,
        value_fn=value_fn,
    )


def _consumed_energy(
    key: str, value_fn: Callable[[SungrowInverter], float | None]
) -> SungrowModbusSensorEntityDescription:
    return SungrowModbusSensorEntityDescription(
        key=key,
        translation_key=key,
        # Every counter it is computed from sits in the same block, so they
        # come from one read and cannot drift apart.
        blocks=(reg.SYSTEM,),
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        lifetime=key.startswith("total_"),
        value_fn=value_fn,
    )


def _running_state(inverter: SungrowInverter) -> str | None:
    code = inverter.value(reg.RUNNING_STATE)
    return RUNNING_STATES.get(code) if isinstance(code, int) else None


SENSORS: tuple[SungrowModbusSensorEntityDescription, ...] = (
    SungrowModbusSensorEntityDescription(
        key="running_state",
        translation_key="running_state",
        blocks=(reg.SYSTEM,),
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(RUNNING_STATES.values())),
        value_fn=_running_state,
    ),
    # PV strings
    _voltage("mppt1_voltage", reg.MPPT1_VOLTAGE),
    _current("mppt1_current", reg.MPPT1_CURRENT, suggested_display_precision=1),
    _computed_power(
        "mppt1_power",
        _product(reg.MPPT1_VOLTAGE, reg.MPPT1_CURRENT),
        reg.MPPT1_VOLTAGE,
        reg.MPPT1_CURRENT,
    ),
    _voltage("mppt2_voltage", reg.MPPT2_VOLTAGE),
    _current("mppt2_current", reg.MPPT2_CURRENT, suggested_display_precision=1),
    _computed_power(
        "mppt2_power",
        _product(reg.MPPT2_VOLTAGE, reg.MPPT2_CURRENT),
        reg.MPPT2_VOLTAGE,
        reg.MPPT2_CURRENT,
    ),
    _voltage("mppt3_voltage", reg.MPPT3_VOLTAGE, exists_fn=_mppt(3)),
    _current(
        "mppt3_current",
        reg.MPPT3_CURRENT,
        suggested_display_precision=1,
        exists_fn=_mppt(3),
    ),
    _computed_power(
        "mppt3_power",
        _product(reg.MPPT3_VOLTAGE, reg.MPPT3_CURRENT),
        reg.MPPT3_VOLTAGE,
        reg.MPPT3_CURRENT,
        exists_fn=_mppt(3),
    ),
    _voltage("mppt4_voltage", reg.MPPT4_VOLTAGE, exists_fn=_mppt(4)),
    _current(
        "mppt4_current",
        reg.MPPT4_CURRENT,
        suggested_display_precision=1,
        exists_fn=_mppt(4),
    ),
    _computed_power(
        "mppt4_power",
        _product(reg.MPPT4_VOLTAGE, reg.MPPT4_CURRENT),
        reg.MPPT4_VOLTAGE,
        reg.MPPT4_CURRENT,
        exists_fn=_mppt(4),
    ),
    _power("total_dc_power", reg.TOTAL_DC_POWER),
    # AC side
    _power("total_active_power", reg.TOTAL_ACTIVE_POWER),
    _register(
        "reactive_power",
        reg.REACTIVE_POWER,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    _register(
        "power_factor",
        reg.POWER_FACTOR,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    _register(
        "grid_frequency",
        reg.GRID_FREQUENCY,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    _voltage("phase_a_voltage", reg.PHASE_A_VOLTAGE),
    _voltage("phase_b_voltage", reg.PHASE_B_VOLTAGE, exists_fn=_three_phase),
    _voltage("phase_c_voltage", reg.PHASE_C_VOLTAGE, exists_fn=_three_phase),
    _current("phase_a_current", reg.PHASE_A_CURRENT, suggested_display_precision=1),
    _current(
        "phase_b_current",
        reg.PHASE_B_CURRENT,
        suggested_display_precision=1,
        exists_fn=_three_phase,
    ),
    _current(
        "phase_c_current",
        reg.PHASE_C_CURRENT,
        suggested_display_precision=1,
        exists_fn=_three_phase,
    ),
    _computed_power(
        "phase_a_power",
        _product(reg.PHASE_A_VOLTAGE, reg.PHASE_A_CURRENT),
        reg.PHASE_A_VOLTAGE,
        reg.PHASE_A_CURRENT,
    ),
    _computed_power(
        "phase_b_power",
        _product(reg.PHASE_B_VOLTAGE, reg.PHASE_B_CURRENT),
        reg.PHASE_B_VOLTAGE,
        reg.PHASE_B_CURRENT,
        exists_fn=_three_phase,
    ),
    _computed_power(
        "phase_c_power",
        _product(reg.PHASE_C_VOLTAGE, reg.PHASE_C_CURRENT),
        reg.PHASE_C_VOLTAGE,
        reg.PHASE_C_CURRENT,
        exists_fn=_three_phase,
    ),
    _temperature("inverter_temperature", reg.INVERTER_TEMPERATURE),
    # House and grid
    _power("load_power", reg.LOAD_POWER),
    # Positive while importing, which is the way Home Assistant's energy
    # dashboard reads a grid power sensor.
    _computed_power("grid_power", _signed(reg.EXPORT_POWER, -1), reg.EXPORT_POWER),
    _computed_power(
        "import_power", _positive_part(reg.EXPORT_POWER, -1), reg.EXPORT_POWER
    ),
    _computed_power(
        "export_power", _positive_part(reg.EXPORT_POWER, 1), reg.EXPORT_POWER
    ),
    # Battery. Its power is positive while discharging, which is the way Home
    # Assistant's energy dashboard reads a battery power sensor.
    _power("battery_power", reg.BATTERY_POWER),
    _computed_power(
        "battery_charging_power",
        _positive_part(reg.BATTERY_POWER, -1),
        reg.BATTERY_POWER,
    ),
    _computed_power(
        "battery_discharging_power",
        _positive_part(reg.BATTERY_POWER, 1),
        reg.BATTERY_POWER,
    ),
    _register(
        "battery_level",
        reg.BATTERY_LEVEL,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    _register(
        "battery_state_of_health",
        reg.BATTERY_STATE_OF_HEALTH,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _register(
        "battery_capacity",
        reg.BATTERY_CAPACITY,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # What the YAML package computes from the SoC limits.
    SungrowModbusSensorEntityDescription(
        key="battery_level_nominal",
        translation_key="battery_level_nominal",
        blocks=(reg.SYSTEM, reg.SOC_LIMITS),
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=_known,
        value_fn=_battery_level_nominal,
    ),
    _battery_energy("battery_charge_nominal", _battery_charge_nominal),
    _battery_energy("battery_charge", _battery_charge),
    _battery_energy("battery_charge_health_rated", _battery_charge_health_rated),
    _voltage("battery_voltage", reg.BATTERY_VOLTAGE),
    _current("battery_current", reg.BATTERY_CURRENT, suggested_display_precision=1),
    _temperature("battery_temperature", reg.BATTERY_TEMPERATURE),
    _current(
        "bms_max_charging_current",
        reg.BMS_MAX_CHARGING_CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _current(
        "bms_max_discharging_current",
        reg.BMS_MAX_DISCHARGING_CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Backup output
    _power("total_backup_power", reg.TOTAL_BACKUP_POWER),
    _power(
        "backup_phase_a_power",
        reg.BACKUP_PHASE_A_POWER,
        entity_registry_enabled_default=False,
    ),
    _power(
        "backup_phase_b_power",
        reg.BACKUP_PHASE_B_POWER,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _power(
        "backup_phase_c_power",
        reg.BACKUP_PHASE_C_POWER,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    # The smart meter, as the inverter relays it. Only valid with the meter
    # wired straight to the inverter, so off until someone wants them.
    _power(
        "meter_active_power",
        reg.METER_ACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    _power(
        "meter_phase_a_active_power",
        reg.METER_PHASE_A_ACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    _power(
        "meter_phase_b_active_power",
        reg.METER_PHASE_B_ACTIVE_POWER,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _power(
        "meter_phase_c_active_power",
        reg.METER_PHASE_C_ACTIVE_POWER,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _voltage(
        "meter_phase_a_voltage",
        reg.METER_PHASE_A_VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    _voltage(
        "meter_phase_b_voltage",
        reg.METER_PHASE_B_VOLTAGE,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _voltage(
        "meter_phase_c_voltage",
        reg.METER_PHASE_C_VOLTAGE,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _current(
        "meter_phase_a_current",
        reg.METER_PHASE_A_CURRENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    _current(
        "meter_phase_b_current",
        reg.METER_PHASE_B_CURRENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    _current(
        "meter_phase_c_current",
        reg.METER_PHASE_C_CURRENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        exists_fn=_three_phase,
    ),
    # Ratings and limits
    SungrowModbusSensorEntityDescription(
        key="rated_output_power",
        translation_key="rated_output_power",
        # Read once while setting up, with the rest of the inverter's identity.
        blocks=(),
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda inverter: inverter.identity.rated_output_power,
    ),
    _power(
        "bdc_rated_power",
        reg.BDC_RATED_POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _power(
        "export_power_limit_min",
        reg.EXPORT_POWER_LIMIT_MIN,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _power(
        "export_power_limit_max",
        reg.EXPORT_POWER_LIMIT_MAX,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Energy counters
    _energy("daily_pv_generation", reg.DAILY_PV_GENERATION),
    _energy("total_pv_generation", reg.TOTAL_PV_GENERATION),
    _energy("daily_pv_export", reg.DAILY_PV_EXPORT),
    _energy("total_pv_export", reg.TOTAL_PV_EXPORT),
    _energy("daily_battery_charge_from_pv", reg.DAILY_BATTERY_CHARGE_FROM_PV),
    _energy("total_battery_charge_from_pv", reg.TOTAL_BATTERY_CHARGE_FROM_PV),
    _energy("daily_direct_consumption", reg.DAILY_DIRECT_CONSUMPTION),
    _energy("total_direct_consumption", reg.TOTAL_DIRECT_CONSUMPTION),
    _energy("daily_battery_charge", reg.DAILY_BATTERY_CHARGE),
    _energy("total_battery_charge", reg.TOTAL_BATTERY_CHARGE),
    _energy("daily_battery_discharge", reg.DAILY_BATTERY_DISCHARGE),
    _energy("total_battery_discharge", reg.TOTAL_BATTERY_DISCHARGE),
    _energy("daily_import", reg.DAILY_IMPORT),
    _energy("total_import", reg.TOTAL_IMPORT),
    _energy("daily_export", reg.DAILY_EXPORT),
    _energy("total_export", reg.TOTAL_EXPORT),
    _energy(
        "daily_output_energy",
        reg.DAILY_OUTPUT_ENERGY,
        entity_registry_enabled_default=False,
    ),
    _energy(
        "total_output_energy",
        reg.TOTAL_OUTPUT_ENERGY,
        entity_registry_enabled_default=False,
    ),
    _consumed_energy(
        "daily_consumption",
        _consumed(
            reg.DAILY_PV_GENERATION,
            reg.DAILY_EXPORT,
            reg.DAILY_IMPORT,
            reg.DAILY_BATTERY_CHARGE,
            reg.DAILY_BATTERY_DISCHARGE,
        ),
    ),
    _consumed_energy(
        "total_consumption",
        _consumed(
            reg.TOTAL_PV_GENERATION,
            reg.TOTAL_EXPORT,
            reg.TOTAL_IMPORT,
            reg.TOTAL_BATTERY_CHARGE,
            reg.TOTAL_BATTERY_DISCHARGE,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus sensor entities based on a config entry."""
    model = entry.runtime_data.inverter.identity.model

    async_add_entities(
        (
            SungrowModbusLifetimeSensorEntity
            if description.lifetime
            else SungrowModbusSensorEntity
        )(entry=entry, description=description)
        for description in SENSORS
        if description.exists_fn(model)
    )


class SungrowModbusSensorEntity(SungrowModbusEntity, SensorEntity):
    """Defines a SunGrow Modbus sensor entity."""

    entity_description: SungrowModbusSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.inverter)


class SungrowModbusLifetimeSensorEntity(SungrowModbusSensorEntity, RestoreSensor):
    """Keeps a lifetime energy counter from ever going down.

    A single low reading fed to a total_increasing sensor registers as a meter
    reset, and everything the counter had reached is counted a second time on
    the next good one. The highest value seen wins, and it is restored across
    restarts so a glitch right after one is caught too.
    """

    _highest_value: float | None = None
    _glitch_logged = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the highest previously seen value."""
        await super().async_added_to_hass()

        data = await self.async_get_last_sensor_data()
        if data is not None and isinstance(data.native_value, (int, float)):
            self._highest_value = data.native_value

    @property
    @override
    def native_value(self) -> StateType:
        """Return the counter, never lower than seen before."""
        value = super().native_value
        if not isinstance(value, (int, float)):
            return self._highest_value

        if self._highest_value is None or value >= self._highest_value:
            self._highest_value = value
            self._glitch_logged = False
            return value

        if not self._glitch_logged:
            LOGGER.warning(
                "%s reported %s kWh, lower than the %s kWh seen before;"
                " ignoring the lower value",
                self.entity_id,
                value,
                self._highest_value,
            )
            self._glitch_logged = True

        return self._highest_value
