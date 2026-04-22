from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import CeramicCapSpec, PolarizedCapSpec

def test_ceramic_group_key_ignores_voltage():
    a = CeramicCapSpec(value=Value(10, "µF"))
    b = CeramicCapSpec(value=Value(10, "µF"))
    assert a.group_key() == b.group_key()
    assert a.display() == "10µF"

def test_polarized_group_key_includes_voltage():
    a = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    b = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(25, "V"))
    assert a.group_key() != b.group_key()
    assert a.display() == "220µF/10V"

def test_polarized_no_voltage_display():
    a = PolarizedCapSpec(value=Value(100, "µF"), voltage=None)
    assert a.display() == "100µF"
    assert a.llm_context() == {"value": "100µF", "voltage": None}
