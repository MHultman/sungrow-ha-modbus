"""The Sungrow hybrid inverter models, by the device type code they report."""

from dataclasses import dataclass
from enum import StrEnum


class Family(StrEnum):
    """The product line a model belongs to."""

    K = "K"  # SH3K6 to SH5K: single phase, the first generation
    RS = "RS"  # SH3.0RS to SH10RS: single phase
    RT = "RT"  # SH5.0RT to SH10RT: three phase
    T = "T"  # SH5T to SH25T: three phase, three MPPTs
    MG = "MG"  # MG5RL, MG6RL: single phase


_THREE_PHASE = {Family.RT, Family.T}


@dataclass(frozen=True, kw_only=True)
class InverterModel:
    """What a model is called and which hardware it has."""

    name: str
    family: Family
    mppt_count: int = 2
    # Whether the model is one this integration knows. An unknown one may not
    # be an SH hybrid at all, so nothing is ever written to it.
    known: bool = True

    @property
    def three_phase(self) -> bool:
        """Return whether the model feeds three phases."""
        return self.family in _THREE_PHASE


def _model(name: str, family: Family, mppt_count: int = 2) -> InverterModel:
    return InverterModel(name=name, family=family, mppt_count=mppt_count)


MODELS: dict[int, InverterModel] = {
    0x0D03: _model("SH5K-V13", Family.K),
    0x0D06: _model("SH3K6", Family.K),
    0x0D07: _model("SH4K6", Family.K),
    0x0D09: _model("SH5K-20", Family.K),
    0x0D0A: _model("SH3K6-30", Family.K),
    0x0D0B: _model("SH4K6-30", Family.K),
    0x0D0C: _model("SH5K-30", Family.K),
    0x0D0D: _model("SH3.6RS", Family.RS),
    0x0D0F: _model("SH5.0RS", Family.RS),
    0x0D10: _model("SH6.0RS", Family.RS),
    0x0D17: _model("SH3.0RS", Family.RS),
    0x0D18: _model("SH4.0RS", Family.RS),
    0x0D1A: _model("SH8.0RS", Family.RS, mppt_count=4),
    0x0D1B: _model("SH10RS", Family.RS, mppt_count=4),
    0x0D27: _model("MG5RL", Family.MG),
    0x0D28: _model("MG6RL", Family.MG),
    0x0E00: _model("SH5.0RT", Family.RT),
    0x0E01: _model("SH6.0RT", Family.RT),
    0x0E02: _model("SH8.0RT", Family.RT),
    0x0E03: _model("SH10RT", Family.RT),
    0x0E08: _model("SH5.0RT-V122", Family.RT),
    0x0E09: _model("SH6.0RT-V122", Family.RT),
    0x0E0A: _model("SH8.0RT-V122", Family.RT),
    0x0E0B: _model("SH10RT-V122", Family.RT),
    0x0E0C: _model("SH5.0RT-V112", Family.RT),
    0x0E0D: _model("SH6.0RT-V112", Family.RT),
    0x0E0E: _model("SH8.0RT-V112", Family.RT),
    0x0E0F: _model("SH10RT-V112", Family.RT),
    0x0E10: _model("SH5.0RT-20", Family.RT),
    0x0E11: _model("SH6.0RT-20", Family.RT),
    0x0E12: _model("SH8.0RT-20", Family.RT),
    0x0E13: _model("SH10RT-20", Family.RT),
    0x0E20: _model("SH5T", Family.T, mppt_count=3),
    0x0E21: _model("SH6T", Family.T, mppt_count=3),
    0x0E22: _model("SH8T", Family.T, mppt_count=3),
    0x0E23: _model("SH10T", Family.T, mppt_count=3),
    0x0E24: _model("SH12T", Family.T, mppt_count=3),
    0x0E25: _model("SH15T", Family.T, mppt_count=3),
    0x0E26: _model("SH20T", Family.T, mppt_count=3),
    0x0E28: _model("SH25T", Family.T, mppt_count=3),
}


def inverter_model(device_type_code: int) -> InverterModel:
    """Return the model behind a device type code.

    A code this table does not know gets read with the most common layout, an
    RT with three phases and two MPPTs, but is marked unknown: Sungrow's SG
    string inverters answer the same identity registers, and the settings an
    SH hybrid takes could mean something else on them.
    """
    if (model := MODELS.get(device_type_code)) is not None:
        return model
    return InverterModel(
        name=f"Unknown (0x{device_type_code:04X})", family=Family.RT, known=False
    )
