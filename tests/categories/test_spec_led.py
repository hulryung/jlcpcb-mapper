import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.led import LEDSpec


def test_group_key_shape():
    spec = LEDSpec(value=Value(0, "RED"))
    assert spec.group_key() == ("led", Value(0, "RED"))


def test_two_equal_specs_have_same_group_key():
    a = LEDSpec(value=Value(0, "RED"))
    b = LEDSpec(value=Value(0, "RED"))
    assert a.group_key() == b.group_key()


def test_different_tokens_have_different_group_keys():
    a = LEDSpec(value=Value(0, "RED"))
    b = LEDSpec(value=Value(0, "GREEN"))
    assert a.group_key() != b.group_key()


def test_display_returns_token():
    spec = LEDSpec(value=Value(0, "RED"))
    assert spec.display() == "RED"


def test_display_ws2812b():
    spec = LEDSpec(value=Value(0, "WS2812B"))
    assert spec.display() == "WS2812B"


def test_llm_context():
    spec = LEDSpec(value=Value(0, "YELLOW"))
    ctx = spec.llm_context()
    assert ctx == {"value": "YELLOW"}


def test_spec_is_frozen():
    spec = LEDSpec(value=Value(0, "RED"))
    with pytest.raises((AttributeError, TypeError)):
        spec.value = Value(0, "GREEN")
