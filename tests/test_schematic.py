from pathlib import Path
from jlcpcb_mapper.schematic import Schematic

FIX = Path(__file__).parent / "fixtures"


def test_parse_uart_schematic_finds_empty_footprints():
    sch = Schematic.load(FIX / "uart.kicad_sch")
    empty = [s for s in sch.instances() if s.footprint == ""]
    refs = {s.reference for s in empty}
    assert "R31" in refs


def test_schematic_instance_has_on_board_and_in_bom_flags():
    sch = Schematic.load(FIX / "uart.kicad_sch")
    insts = sch.instances()
    assert len(insts) > 0
    # default true for all in uart fixture
    assert all(i.on_board for i in insts)
    # in_bom should be parsed too
    for i in insts:
        assert isinstance(i.in_bom, bool)


def test_roundtrip_byte_identical(tmp_path):
    src = FIX / "uart.kicad_sch"
    dst = tmp_path / "copy.kicad_sch"
    sch = Schematic.load(src)
    sch.save(dst)
    # Round-trip MUST produce identical bytes when no edits made.
    assert src.read_bytes() == dst.read_bytes(), "kiutils round-trip introduced diff noise"


def test_update_footprint_changes_only_target(tmp_path):
    src_original = FIX / "uart.kicad_sch"
    src = tmp_path / "uart.kicad_sch"
    src.write_bytes(src_original.read_bytes())
    dst = tmp_path / "edited.kicad_sch"
    sch = Schematic.load(src)
    inst = next(s for s in sch.instances() if s.reference == "R31")
    sch.set_footprint(inst, "Resistor_SMD:R_0402_1005Metric")
    sch.set_lcsc(inst, "C17168")
    sch.save(dst)
    sch2 = Schematic.load(dst)
    r31 = next(s for s in sch2.instances() if s.reference == "R31")
    assert r31.footprint == "Resistor_SMD:R_0402_1005Metric"
    assert r31.lcsc == "C17168"
    # Other symbols untouched
    other = next(s for s in sch2.instances() if s.reference == "R36")
    assert other.footprint == ""
