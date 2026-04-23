"""Tests for ConnectorSpec."""
import pytest
from jlcpcb_mapper.categories.spec.connector import ConnectorSpec


def _spec(structure: str, pins: int, value: str) -> ConnectorSpec:
    return ConnectorSpec(structure=structure, pins=pins, value=value)


# --- group_key tests ---

def test_group_key_1xn():
    s = _spec("1xN", 5, "")
    assert s.group_key() == ("connector", "1xN", 5, "")


def test_group_key_2xn_with_value():
    s = _spec("2xN", 10, "JST")
    assert s.group_key() == ("connector", "2xN", 10, "JST")


def test_group_key_generic():
    s = _spec("generic", 0, "USBC-XYZ")
    assert s.group_key() == ("connector", "generic", 0, "USBC-XYZ")


# --- display tests ---

def test_display_1xn_no_value():
    s = _spec("1xN", 6, "")
    assert s.display() == "1x6"


def test_display_1xn_with_value():
    s = _spec("1xN", 6, "JST-PH-6")
    assert s.display() == "1x6 JST-PH-6"


def test_display_2xn_no_value():
    s = _spec("2xN", 10, "")
    assert s.display() == "2x10"


def test_display_2xn_with_value():
    s = _spec("2xN", 5, "IDC")
    assert s.display() == "2x5 IDC"


def test_display_generic_with_value():
    s = _spec("generic", 0, "USBC-XYZ")
    assert s.display() == "USBC-XYZ"


def test_display_generic_empty_value():
    s = _spec("generic", 0, "")
    assert s.display() == "connector"


# --- llm_context tests ---

def test_llm_context_1xn():
    s = _spec("1xN", 5, "JST")
    ctx = s.llm_context()
    assert ctx == {"structure": "1xN", "pins": 5, "value": "JST"}


def test_llm_context_generic():
    s = _spec("generic", 0, "")
    ctx = s.llm_context()
    assert ctx == {"structure": "generic", "pins": 0, "value": ""}


# --- frozen (immutability) test ---

def test_spec_is_frozen():
    s = _spec("1xN", 5, "test")
    with pytest.raises((AttributeError, TypeError)):
        s.pins = 10  # type: ignore[misc]
