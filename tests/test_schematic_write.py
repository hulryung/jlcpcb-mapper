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


def test_multiple_mutations_preserve_all_offsets(tmp_path):
    """Bulk-apply LCSC+Footprint to many instances; every one must receive both."""
    src = tmp_path / "uart.kicad_sch"
    src.write_bytes((FIX / "uart.kicad_sch").read_bytes())
    sch = Schematic.load(src)
    # Pick all resistor instances with empty Footprint
    targets = [i for i in sch.instances()
               if i.lib_id.startswith("Device:R") and i.footprint == ""]
    assert len(targets) >= 5, "fixture expected to have multiple empty resistor instances"
    for inst in targets:
        sch.set_lcsc(inst, "C17168")
        sch.set_footprint(inst, "Resistor_SMD:R_0402_1005Metric")
    # Write to a new path so we can reload and re-check
    dst = tmp_path / "out.kicad_sch"
    sch.save(dst)
    sch2 = Schematic.load(dst)
    # Every target ref must now have both LCSC and Footprint set
    by_ref_new = {i.reference: i for i in sch2.instances()}
    missing = []
    for t in targets:
        i2 = by_ref_new[t.reference]
        if i2.lcsc != "C17168" or i2.footprint != "Resistor_SMD:R_0402_1005Metric":
            missing.append((t.reference, i2.lcsc, i2.footprint))
    assert not missing, f"Mutations lost on {len(missing)} refs: {missing[:10]}"
