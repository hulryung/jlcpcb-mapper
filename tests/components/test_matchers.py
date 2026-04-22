from jlcpcb_mapper.components.matchers import LibIdAny, LibIdPrefix

def test_libidany_exact_and_suffixed():
    m = LibIdAny(["Device:CP", "Device:C_Polarized"])
    assert m.matches("Device:CP")
    assert m.matches("Device:CP_Small")
    assert m.matches("Device:C_Polarized")
    assert m.matches("Device:C_Polarized_Small")
    assert not m.matches("Device:C")
    assert not m.matches("Device:R")

def test_libidprefix_matches_prefix_only():
    m = LibIdPrefix(["Connector_Generic:Conn_02x"])
    assert m.matches("Connector_Generic:Conn_02x05_Odd_Even")
    assert not m.matches("Connector_Generic:Conn_01x05")
