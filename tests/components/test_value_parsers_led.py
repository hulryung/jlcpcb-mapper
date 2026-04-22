import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.led import LEDSpec
from jlcpcb_mapper.components.value_parsers import LEDValueParser


def _spec(token: str) -> LEDSpec:
    return LEDSpec(value=Value(0, token))


def test_red():
    assert LEDValueParser().parse("RED") == _spec("RED")


def test_lowercase_red_upcased():
    assert LEDValueParser().parse("red") == _spec("RED")


def test_ws2812b():
    assert LEDValueParser().parse("WS2812B") == _spec("WS2812B")


def test_green_trimmed():
    assert LEDValueParser().parse("  GREEN  ") == _spec("GREEN")


def test_yellow():
    assert LEDValueParser().parse("yellow") == _spec("YELLOW")


def test_empty_returns_none():
    assert LEDValueParser().parse("") is None


def test_whitespace_only_returns_none():
    assert LEDValueParser().parse("   ") is None


def test_mixed_case_ws2812b():
    assert LEDValueParser().parse("ws2812b") == _spec("WS2812B")
