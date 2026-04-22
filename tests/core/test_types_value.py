from jlcpcb_mapper.core.types import Value

def test_value_equality():
    assert Value(10.0, "kΩ") == Value(10.0, "kΩ")
    assert Value(10.0, "kΩ") != Value(10.0, "Ω")

def test_value_is_hashable():
    {Value(1, "Ω"): "ok"}

def test_value_display_integer_magnitude():
    assert Value(10, "kΩ").display() == "10kΩ"

def test_value_display_fractional_magnitude_drops_trailing_zero():
    assert Value(4.7, "µF").display() == "4.7µF"
    assert Value(4.70, "µF").display() == "4.7µF"

def test_value_frozen():
    import dataclasses
    v = Value(1, "Ω")
    try:
        v.magnitude = 2  # type: ignore
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Value should be frozen")
