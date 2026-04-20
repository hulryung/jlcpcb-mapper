from pathlib import Path
from jlcpcb_mapper.schematic import Schematic, atomic_update

FIX = Path(__file__).parent / "fixtures"

def test_atomic_update_creates_backup_and_commits(tmp_path):
    src = tmp_path / "uart.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    backup_dir = tmp_path / ".jlcpcb-mapper" / "backups" / "ts"
    def mutate(sch: Schematic):
        r31 = next(i for i in sch.instances() if i.reference == "R31")
        sch.set_footprint(r31, "Resistor_SMD:R_0402_1005Metric")
        sch.set_lcsc(r31, "C17168")
    atomic_update(src, mutate, backup_dir=backup_dir)
    assert (backup_dir / "uart.kicad_sch").exists()
    text = src.read_text()
    assert "Resistor_SMD:R_0402_1005Metric" in text
    assert "C17168" in text

def test_atomic_update_nomutation_preserves_bytes(tmp_path):
    src = tmp_path / "uart.kicad_sch"
    orig = (FIX / "uart.kicad_sch").read_bytes()
    src.write_bytes(orig)
    backup_dir = tmp_path / ".jlcpcb-mapper" / "backups" / "ts"
    atomic_update(src, lambda sch: None, backup_dir=backup_dir)
    # No-op mutation must preserve byte identity
    assert src.read_bytes() == orig
    assert (backup_dir / "uart.kicad_sch").read_bytes() == orig
