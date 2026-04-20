from jlcpcb_mapper.grouper import group_instances, GroupKey, Group
from jlcpcb_mapper.schematic import SymbolInstance

def mk(ref, value, lib_id, footprint="", lcsc="", dnp=False):
    return SymbolInstance(ref, value, lib_id, footprint, lcsc, dnp, 0, 0)

def test_groups_same_value_same_package():
    defaults = {"resistor": {"package": "0402"}, "capacitor": {"package": "0402"}}
    insts = [
        mk("R1", "0", "Device:R_Small_US"),
        mk("R2", "0", "Device:R_Small_US"),
        mk("R3", "1K", "Device:R_Small_US"),
        mk("C1", "2.2uF", "Device:C_Small"),
    ]
    groups = group_instances(insts, defaults)
    assert len(groups) == 3
    g_zero = next(g for g in groups if g.key.value == "0Ω")
    assert {i.reference for i in g_zero.instances} == {"R1", "R2"}

def test_power_symbols_filtered_out():
    defaults = {"resistor": {"package": "0402"}}
    insts = [
        mk("#PWR01", "GND", "power:GND"),
        mk("R1", "0", "Device:R_Small_US"),
    ]
    groups = group_instances(insts, defaults)
    assert all(g.key.category != "power" for g in groups)
    assert len(groups) == 1

def test_connector_grouping_by_pin_count():
    insts = [
        mk("J1", "Conn_6p", "Connector_Generic:Conn_01x06"),
        mk("J2", "Conn_6p_other", "Connector_Generic:Conn_01x06"),
        mk("J3", "Conn_1p", "Connector_Generic:Conn_01x01"),
    ]
    groups = group_instances(insts, {})
    cats = sorted({g.key.category for g in groups})
    assert cats == ["connector_1x1", "connector_1x6"]
