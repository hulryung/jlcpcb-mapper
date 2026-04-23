"""Smallest valid KiCad-9 schematic bytes for round-trip tests."""

MINIMAL_SCH_TEMPLATE = '''(kicad_sch
\t(version 20231120)
\t(generator "jlcpcb-mapper-tests")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols
\t)
\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at 50 50 0)
\t\t(unit 1)
\t\t(uuid "00000000-0000-0000-0000-{ref_pad:0>12}")
\t\t(property "Reference" "{reference}"
\t\t\t(at 0 0 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at 0 0 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Footprint" "{footprint}"
\t\t\t(at 0 0 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t)
)
'''


def minimal_sch_one_symbol(*, reference: str, lib_id: str, value: str, footprint: str = "") -> str:
    return MINIMAL_SCH_TEMPLATE.format(
        reference=reference, lib_id=lib_id, value=value,
        footprint=footprint,
        ref_pad=reference.replace("C", "").replace("R", "").replace("U", "").replace("L", "").replace("D", "") or "0",
    )
