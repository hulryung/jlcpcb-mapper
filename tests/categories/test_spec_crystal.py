import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.crystal import CrystalSpec


def test_group_key_shape():
    spec = CrystalSpec(value=Value(16, "MHz"))
    assert spec.group_key() == ("crystal", Value(16, "MHz"))


def test_two_equal_specs_have_same_group_key():
    a = CrystalSpec(value=Value(16, "MHz"))
    b = CrystalSpec(value=Value(16, "MHz"))
    assert a.group_key() == b.group_key()


def test_different_frequencies_have_different_group_keys():
    a = CrystalSpec(value=Value(16, "MHz"))
    b = CrystalSpec(value=Value(32.768, "kHz"))
    assert a.group_key() != b.group_key()


def test_display_integer_mhz():
    spec = CrystalSpec(value=Value(16, "MHz"))
    assert spec.display() == "16MHz"


def test_display_fractional_khz():
    spec = CrystalSpec(value=Value(32.768, "kHz"))
    assert spec.display() == "32.768kHz"


def test_display_hz():
    spec = CrystalSpec(value=Value(400, "Hz"))
    assert spec.display() == "400Hz"


def test_llm_context():
    spec = CrystalSpec(value=Value(16, "MHz"))
    ctx = spec.llm_context()
    assert ctx == {"value": "16MHz"}


def test_llm_context_khz():
    spec = CrystalSpec(value=Value(32.768, "kHz"))
    ctx = spec.llm_context()
    assert ctx == {"value": "32.768kHz"}


def test_spec_is_frozen():
    spec = CrystalSpec(value=Value(16, "MHz"))
    with pytest.raises((AttributeError, TypeError)):
        spec.value = Value(8, "MHz")
