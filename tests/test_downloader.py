from pathlib import Path
from unittest.mock import patch
from jlcpcb_mapper.downloader import download_footprint, ensure_fp_lib_table_entry


def test_ensure_fp_lib_table_adds_entry(tmp_path):
    table = tmp_path / "fp-lib-table"
    table.write_text("(fp_lib_table\n)")
    changed = ensure_fp_lib_table_entry(table, lib_name="LCSC", uri="${KIPRJMOD}/libs/lcsc/footprints.pretty")
    assert changed is True
    text = table.read_text()
    assert '(name "LCSC")' in text
    assert '${KIPRJMOD}/libs/lcsc/footprints.pretty' in text


def test_ensure_fp_lib_table_idempotent(tmp_path):
    table = tmp_path / "fp-lib-table"
    table.write_text("(fp_lib_table\n)")
    ensure_fp_lib_table_entry(table, "LCSC", "${KIPRJMOD}/libs/lcsc/footprints.pretty")
    changed = ensure_fp_lib_table_entry(table, "LCSC", "${KIPRJMOD}/libs/lcsc/footprints.pretty")
    assert changed is False


def test_download_footprint_success(tmp_path):
    out_dir = tmp_path / "libs/lcsc/footprints.pretty"
    with patch("jlcpcb_mapper.downloader._easyeda_to_kicad_mod") as mock:
        mock.return_value = ("C12345_QFN", "(module ... )")
        path = download_footprint("C12345", out_dir)
    assert path is not None
    assert path.exists()
    assert path.name.startswith("C12345")


def test_download_footprint_failure_returns_none(tmp_path):
    out_dir = tmp_path / "libs/lcsc/footprints.pretty"
    with patch("jlcpcb_mapper.downloader._easyeda_to_kicad_mod", return_value=None):
        path = download_footprint("C99999", out_dir)
    assert path is None
