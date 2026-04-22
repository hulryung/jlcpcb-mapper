"""Tests for ICSpec."""
import pytest
from jlcpcb_mapper.categories.spec.ic import ICSpec


def test_mpn_stored():
    spec = ICSpec(mpn="STM32F031K6T6")
    assert spec.mpn == "STM32F031K6T6"


def test_group_key():
    spec = ICSpec(mpn="STM32F031K6T6")
    assert spec.group_key() == ("ic", "STM32F031K6T6")


def test_display():
    spec = ICSpec(mpn="AO3400A")
    assert spec.display() == "AO3400A"


def test_llm_context():
    spec = ICSpec(mpn="LM2596S-3.3")
    ctx = spec.llm_context()
    assert ctx == {"mpn": "LM2596S-3.3"}


def test_frozen():
    spec = ICSpec(mpn="STM32F031K6T6")
    with pytest.raises((AttributeError, TypeError)):
        spec.mpn = "something_else"  # type: ignore[misc]


def test_equality():
    a = ICSpec(mpn="STM32F031K6T6")
    b = ICSpec(mpn="STM32F031K6T6")
    c = ICSpec(mpn="AO3400A")
    assert a == b
    assert a != c
