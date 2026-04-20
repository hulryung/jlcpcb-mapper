from pathlib import Path
from jlcpcb_mapper.project import load_project, select_targets

FIX = Path(__file__).parent / "fixtures"

def test_load_project_enumerates_sheets(tmp_path):
    src = tmp_path / "proj.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    pro = tmp_path / "proj.kicad_pro"; pro.write_text("{}")
    proj = load_project(pro)
    assert len(proj.schematics) >= 1
    assert any(p.name == "proj.kicad_sch" for p in proj.schematics)

def test_select_targets_default_skips_power_and_already_mapped(tmp_path):
    src = tmp_path / "proj.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    pro = tmp_path / "proj.kicad_pro"; pro.write_text("{}")
    proj = load_project(pro)
    targets = select_targets(proj, fill_lcsc_only=False, include_dnp=False)
    # Power symbols excluded
    assert all(not t.inst.lib_id.startswith("power:") for t in targets)
    # Default mode: footprint must be empty
    assert all(t.inst.footprint == "" for t in targets)
    # J5 already has Footprint in uart.kicad_sch, should NOT be in targets
    assert all(t.inst.reference != "J5" for t in targets)
    # R31 is an empty-footprint resistor
    assert any(t.inst.reference == "R31" for t in targets)

def test_select_targets_fill_lcsc_only(tmp_path):
    src = tmp_path / "proj.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    pro = tmp_path / "proj.kicad_pro"; pro.write_text("{}")
    proj = load_project(pro)
    targets = select_targets(proj, fill_lcsc_only=True, include_dnp=False)
    # J5 has Footprint but check its LCSC: in the fixture J5 already has LCSC C262679
    # so J5 should NOT be a target in fill_lcsc_only mode
    assert all(t.inst.reference != "J5" for t in targets)
    # All targets in fill_lcsc_only mode must have empty LCSC
    assert all(t.inst.lcsc == "" for t in targets)

def test_target_carries_schematic_path(tmp_path):
    src = tmp_path / "proj.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    pro = tmp_path / "proj.kicad_pro"; pro.write_text("{}")
    proj = load_project(pro)
    targets = select_targets(proj, fill_lcsc_only=False, include_dnp=False)
    assert all(t.sch_path == src for t in targets)
