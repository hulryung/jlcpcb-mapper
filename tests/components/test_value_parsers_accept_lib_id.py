"""Regression tests: every existing value parser accepts lib_id= kwarg without error.

This guards against protocol regressions after the ValueParser protocol was
extended to include an optional lib_id keyword argument.
"""
from jlcpcb_mapper.components.value_parsers import (
    CapValueParser, ResistorValueParser, InductorValueParser,
    LEDValueParser, CrystalValueParser, ICValueParser,
)


def test_cap_parser_accepts_lib_id_kwarg():
    p = CapValueParser(keep_voltage=False)
    # Same behavior as without lib_id
    assert p.parse("10uF", lib_id="Device:C") == p.parse("10uF")


def test_resistor_parser_accepts_lib_id_kwarg():
    p = ResistorValueParser()
    assert p.parse("10k", lib_id="Device:R") == p.parse("10k")


def test_inductor_parser_accepts_lib_id_kwarg():
    p = InductorValueParser()
    assert p.parse("33uH", lib_id="Device:L") == p.parse("33uH")


def test_led_parser_accepts_lib_id_kwarg():
    p = LEDValueParser()
    assert p.parse("RED", lib_id="Device:LED") == p.parse("RED")


def test_crystal_parser_accepts_lib_id_kwarg():
    p = CrystalValueParser()
    assert p.parse("16MHz", lib_id="Device:Crystal") == p.parse("16MHz")


def test_ic_parser_accepts_lib_id_kwarg():
    p = ICValueParser()
    assert p.parse("STM32F031K6T6", lib_id="MCU_ST_STM32F0:STM32F031K6Tx") == p.parse("STM32F031K6T6")
