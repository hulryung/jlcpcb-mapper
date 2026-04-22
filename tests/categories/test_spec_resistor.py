from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.resistor import ResistorSpec


def test_group_key_shape():
    spec = ResistorSpec(value=Value(10000, "Ω"))
    assert spec.group_key() == ("resistor", Value(10000, "Ω"))


def test_two_equal_specs_have_same_group_key():
    a = ResistorSpec(value=Value(10000, "Ω"))
    b = ResistorSpec(value=Value(10000, "Ω"))
    assert a.group_key() == b.group_key()


def test_different_values_have_different_group_keys():
    a = ResistorSpec(value=Value(10000, "Ω"))
    b = ResistorSpec(value=Value(4700, "Ω"))
    assert a.group_key() != b.group_key()


def test_display_integer():
    spec = ResistorSpec(value=Value(10000, "Ω"))
    assert spec.display() == "10000Ω"


def test_display_zero():
    spec = ResistorSpec(value=Value(0, "Ω"))
    assert spec.display() == "0Ω"


def test_llm_context():
    spec = ResistorSpec(value=Value(10000, "Ω"))
    ctx = spec.llm_context()
    assert ctx == {"value": "10000Ω"}


def test_spec_is_frozen():
    import pytest
    spec = ResistorSpec(value=Value(10000, "Ω"))
    with pytest.raises((AttributeError, TypeError)):
        spec.value = Value(100, "Ω")
