"""The highest values the inverter's power settings sensibly take."""

from collections.abc import Callable

from . import registers as reg
from .inverter import SungrowInverter
from .registers import Register

# For an inverter that reports no rating at all, which none should.
FALLBACK_POWER_CEILING = 10_000


def battery_power_ceiling(register: Register) -> Callable[[SungrowInverter], float]:
    """Return the most a battery power setting can sensibly be set to.

    That is what the battery converter or the inverter is rated for, unless
    the setting already holds more: some inverters ship with a charge limit
    above their converter's rating, and the control has to be able to show it.
    """

    def ceiling(inverter: SungrowInverter) -> float:
        candidates = (
            inverter.value(reg.BDC_RATED_POWER),
            inverter.identity.rated_output_power,
            inverter.value(register),
        )
        return max(
            (value for value in candidates if isinstance(value, (int, float))),
            default=FALLBACK_POWER_CEILING,
        )

    return ceiling


def reported(
    register: Register, fallback: Callable[[SungrowInverter], float]
) -> Callable[[SungrowInverter], float]:
    """Return a limit the inverter reports, or a fallback while it has none."""

    def limit(inverter: SungrowInverter) -> float:
        value = inverter.value(register)
        return value if isinstance(value, (int, float)) else fallback(inverter)

    return limit


def rated_output(inverter: SungrowInverter) -> float:
    """Return what the inverter is rated to put out."""
    return inverter.identity.rated_output_power or FALLBACK_POWER_CEILING


def capped(ceiling: float, cap: int | None) -> float:
    """Return a battery power ceiling, held to the cap the user set, if any."""
    return ceiling if cap is None else min(ceiling, cap)
