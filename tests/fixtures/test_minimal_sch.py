from pathlib import Path
from jlcpcb_mapper.io.schematic import Schematic
from tests.fixtures.minimal_sch import minimal_sch_one_symbol


def test_minimal_sch_parses(tmp_path: Path):
    p = tmp_path / "x.kicad_sch"
    p.write_text(minimal_sch_one_symbol(
        reference="C12", lib_id="Device:CP",
        value="220uF/10V", footprint="",
    ))
    sch = Schematic.load(p)
    insts = sch.instances()
    assert len(insts) == 1
    assert insts[0].reference == "C12"
    assert insts[0].lib_id == "Device:CP"
    assert insts[0].value == "220uF/10V"
    assert insts[0].footprint == ""
