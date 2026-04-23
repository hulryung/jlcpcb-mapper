"""Tests for ConnectorValueParser."""
from jlcpcb_mapper.components.value_parsers import ConnectorValueParser
from jlcpcb_mapper.categories.spec.connector import ConnectorSpec


def _parse(raw: str, lib_id=None) -> ConnectorSpec:
    return ConnectorValueParser().parse(raw, lib_id=lib_id)


# --- 1xN cases ---

def test_1xn_05_odd_even():
    result = _parse("", lib_id="Connector_Generic:Conn_01x05_Odd_Even")
    assert result == ConnectorSpec("1xN", 5, "")


def test_1xn_06_bare():
    result = _parse("JST-PH-6", lib_id="Connector_Generic:Conn_01x06")
    assert result == ConnectorSpec("1xN", 6, "JST-PH-6")


def test_1xn_value_preserved():
    result = _parse("  JST-PH-6  ", lib_id="Connector_Generic:Conn_01x06")
    assert result == ConnectorSpec("1xN", 6, "JST-PH-6")


def test_1xn_02():
    result = _parse("", lib_id="Connector_Generic:Conn_01x02")
    assert result == ConnectorSpec("1xN", 2, "")


def test_1xn_10():
    result = _parse("", lib_id="Connector_Generic:Conn_01x10_Pin")
    assert result == ConnectorSpec("1xN", 10, "")


# --- 2xN cases ---

def test_2xn_10_odd_even():
    result = _parse("", lib_id="Connector_Generic:Conn_02x10_Odd_Even")
    assert result == ConnectorSpec("2xN", 10, "")


def test_2xn_05():
    result = _parse("IDC-10", lib_id="Connector_Generic:Conn_02x05")
    assert result == ConnectorSpec("2xN", 5, "IDC-10")


def test_2xn_03():
    result = _parse("", lib_id="Connector_Generic:Conn_02x03_Odd_Even")
    assert result == ConnectorSpec("2xN", 3, "")


# --- generic cases ---

def test_generic_usb_c():
    result = _parse("USBC-XYZ", lib_id="Connector_USB:USB_C_Receptacle_Palconn_UTC16-G")
    assert result == ConnectorSpec("generic", 0, "USBC-XYZ")


def test_generic_molex():
    result = _parse("", lib_id="Connector_Molex:Molex_PicoBlade_53047-0210")
    assert result == ConnectorSpec("generic", 0, "")


def test_no_lib_id():
    result = _parse("FOO", lib_id=None)
    assert result == ConnectorSpec("generic", 0, "FOO")


def test_no_lib_id_empty_value():
    result = _parse("", lib_id=None)
    assert result == ConnectorSpec("generic", 0, "")


# --- never returns None ---

def test_never_returns_none_with_lib_id():
    assert _parse("", lib_id="Connector_Generic:Conn_01x01") is not None


def test_never_returns_none_without_lib_id():
    assert _parse("", lib_id=None) is not None


def test_never_returns_none_generic():
    assert _parse("USBC-XYZ", lib_id="Connector_USB:USB_C_Receptacle") is not None
