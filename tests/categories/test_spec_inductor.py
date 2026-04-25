import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.inductor import InductorSpec


def test_group_key_shape():
    spec = InductorSpec(value=Value(33, "µH"))
    assert spec.group_key() == ("inductor", Value(33, "µH"), None)


def test_group_key_includes_current():
    a = InductorSpec(value=Value(33, "µH"))
    b = InductorSpec(value=Value(33, "µH"), current_a=2.0)
    assert a.group_key() != b.group_key()


def test_display_with_current():
    assert InductorSpec(value=Value(4.7, "µH"), current_a=2.0).display() == "4.7µH/2A"
    assert InductorSpec(value=Value(4.7, "µH"), current_a=0.35).display() == "4.7µH/350mA"


def test_llm_context_with_current():
    ctx = InductorSpec(value=Value(33, "µH"), current_a=3.0).llm_context()
    assert ctx == {"value": "33µH", "current_a_min": 3.0}


def test_two_equal_specs_have_same_group_key():
    a = InductorSpec(value=Value(33, "µH"))
    b = InductorSpec(value=Value(33, "µH"))
    assert a.group_key() == b.group_key()


def test_different_values_have_different_group_keys():
    a = InductorSpec(value=Value(33, "µH"))
    b = InductorSpec(value=Value(10, "µH"))
    assert a.group_key() != b.group_key()


def test_different_units_have_different_group_keys():
    a = InductorSpec(value=Value(10, "µH"))
    b = InductorSpec(value=Value(10, "nH"))
    assert a.group_key() != b.group_key()


def test_display():
    spec = InductorSpec(value=Value(33, "µH"))
    assert spec.display() == "33µH"


def test_display_fractional():
    spec = InductorSpec(value=Value(4.7, "µH"))
    assert spec.display() == "4.7µH"


def test_llm_context():
    spec = InductorSpec(value=Value(33, "µH"))
    ctx = spec.llm_context()
    assert ctx == {"value": "33µH"}


def test_spec_is_frozen():
    spec = InductorSpec(value=Value(33, "µH"))
    with pytest.raises((AttributeError, TypeError)):
        spec.value = Value(10, "µH")
