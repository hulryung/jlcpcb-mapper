from unittest.mock import patch
from jlcpcb_mapper.resolver import resolve_footprint
from jlcpcb_mapper.io.parts_db import PartRow

def row(lcsc="C1", package="0402"):
    return PartRow(lcsc, "Chip Resistor", "m", "p", package, "desc", 1, 0, 1000, 0.1)

def test_resolver_uses_kicad_builtin(tmp_path):
    result = resolve_footprint(
        category="resistor",
        part=row(package="0402"),
        out_dir=tmp_path / "libs" / "lcsc" / "footprints.pretty",
        overrides={},
    )
    assert result.footprint == "Resistor_SMD:R_0402_1005Metric"
    assert result.downloaded is False
    assert result.download_failed is False

def test_resolver_downloads_when_unknown(tmp_path):
    out = tmp_path / "libs" / "lcsc" / "footprints.pretty"
    def fake_download(lcsc, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{lcsc}_QFN.kicad_mod"
        p.write_text("(module)")
        return p
    with patch("jlcpcb_mapper.resolver.download_footprint", side_effect=fake_download):
        result = resolve_footprint(
            category="ic",
            part=row(lcsc="C12345", package="QFN-24"),
            out_dir=out,
            overrides={},
        )
    assert result.footprint == "LCSC:C12345_QFN"
    assert result.downloaded is True
    assert result.download_failed is False

def test_resolver_leaves_empty_when_download_fails(tmp_path):
    out = tmp_path / "libs" / "lcsc" / "footprints.pretty"
    with patch("jlcpcb_mapper.resolver.download_footprint", return_value=None):
        result = resolve_footprint(
            category="ic",
            part=row(lcsc="C99", package="EXOTIC"),
            out_dir=out,
            overrides={},
        )
    assert result.footprint == ""
    assert result.downloaded is False
    assert result.download_failed is True

def test_resolver_override_wins(tmp_path):
    result = resolve_footprint(
        category="resistor",
        part=row(package="0402"),
        out_dir=tmp_path / "libs",
        overrides={"resistor,0402": "Custom:MyR_0402"},
    )
    assert result.footprint == "Custom:MyR_0402"
    assert result.downloaded is False
