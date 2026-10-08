"""The Sungrow hybrid inverter models, by the device type code they report."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class InverterModel:
    """What a model is called and which hardware it has."""

    name: str
    mppt_count: int = 2
    three_phase: bool


def _single_phase(name: str, mppt_count: int = 2) -> InverterModel:
    return InverterModel(name=name, mppt_count=mppt_count, three_phase=False)


def _three_phase(name: str, mppt_count: int = 2) -> InverterModel:
    return InverterModel(name=name, mppt_count=mppt_count, three_phase=True)


MODELS: dict[int, InverterModel] = {
    0x0D03: _single_phase("SH5K-V13"),
    0x0D06: _single_phase("SH3K6"),
    0x0D07: _single_phase("SH4K6"),
    0x0D09: _single_phase("SH5K-20"),
    0x0D0A: _single_phase("SH3K6-30"),
    0x0D0B: _single_phase("SH4K6-30"),
    0x0D0C: _single_phase("SH5K-30"),
    0x0D0D: _single_phase("SH3.6RS"),
    0x0D0F: _single_phase("SH5.0RS"),
    0x0D10: _single_phase("SH6.0RS"),
    0x0D17: _single_phase("SH3.0RS"),
    0x0D18: _single_phase("SH4.0RS"),
    0x0D1A: _single_phase("SH8.0RS", mppt_count=4),
    0x0D1B: _single_phase("SH10RS", mppt_count=4),
    0x0D27: _single_phase("MG5RL"),
    0x0D28: _single_phase("MG6RL"),
    0x0E00: _three_phase("SH5.0RT"),
    0x0E01: _three_phase("SH6.0RT"),
    0x0E02: _three_phase("SH8.0RT"),
    0x0E03: _three_phase("SH10RT"),
    0x0E08: _three_phase("SH5.0RT-V122"),
    0x0E09: _three_phase("SH6.0RT-V122"),
    0x0E0A: _three_phase("SH8.0RT-V122"),
    0x0E0B: _three_phase("SH10RT-V122"),
    0x0E0C: _three_phase("SH5.0RT-V112"),
    0x0E0D: _three_phase("SH6.0RT-V112"),
    0x0E0E: _three_phase("SH8.0RT-V112"),
    0x0E0F: _three_phase("SH10RT-V112"),
    0x0E10: _three_phase("SH5.0RT-20"),
    0x0E11: _three_phase("SH6.0RT-20"),
    0x0E12: _three_phase("SH8.0RT-20"),
    0x0E13: _three_phase("SH10RT-20"),
    0x0E20: _three_phase("SH5T", mppt_count=3),
    0x0E21: _three_phase("SH6T", mppt_count=3),
    0x0E22: _three_phase("SH8T", mppt_count=3),
    0x0E23: _three_phase("SH10T", mppt_count=3),
    0x0E24: _three_phase("SH12T", mppt_count=3),
    0x0E25: _three_phase("SH15T", mppt_count=3),
    0x0E26: _three_phase("SH20T", mppt_count=3),
    0x0E28: _three_phase("SH25T", mppt_count=3),
}


def inverter_model(device_type_code: int) -> InverterModel:
    """Return the model behind a device type code.

    A code this table does not know yet is still a Sungrow hybrid, so it gets
    the most common layout rather than being refused: three phases, as most SH
    hybrids are, and two MPPTs, which every model has.
    """
    if (model := MODELS.get(device_type_code)) is not None:
        return model
    return _three_phase(f"SH (0x{device_type_code:04X})")
