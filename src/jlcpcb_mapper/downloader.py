from __future__ import annotations
from pathlib import Path


def _easyeda_to_kicad_mod(lcsc: str) -> tuple[str, str] | None:
    """Fetch a JLCPCB/EasyEDA component by LCSC and convert to a KiCad
    footprint (.kicad_mod text). Returns (footprint_name, text) or None on failure.

    Implementation adapts to easyeda2kicad's API. Import paths may vary between
    versions; wrap in try/except so missing dependencies/errors degrade gracefully.
    """
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
        from easyeda2kicad.easyeda.parameters_easyeda import EasyedaFootprint
        from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad
    except Exception:
        return None
    try:
        api = EasyedaApi()
        cad = api.get_cad_data_of_component(lcsc)
        if not cad or "packageDetail" not in cad:
            return None
        fp = EasyedaFootprint(**cad["packageDetail"]["dataStr"])
        exp = ExporterFootprintKicad(footprint=fp)
        name = getattr(exp.output, "name", None) or f"{lcsc}_fp"
        return name, exp.get_ki_footprint()
    except Exception:
        return None


def download_footprint(lcsc: str, out_dir: Path) -> Path | None:
    res = _easyeda_to_kicad_mod(lcsc)
    if res is None:
        return None
    name, text = res
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{lcsc}_{name}.kicad_mod"
    path.write_text(text)
    return path


def ensure_fp_lib_table_entry(
    table_path: Path,
    lib_name: str,
    uri: str,
    lib_type: str = "KiCad",
) -> bool:
    """Insert a (lib ...) entry into fp-lib-table if not present.
    Returns True if the file was modified.
    """
    text = table_path.read_text()
    needle = f'(name "{lib_name}")'
    if needle in text:
        return False
    entry = f'  (lib (name "{lib_name}")(type "{lib_type}")(uri "{uri}")(options "")(descr ""))\n'
    stripped = text.rstrip()
    if stripped.endswith(")"):
        new_text = stripped[:-1].rstrip() + "\n" + entry + ")\n"
    else:
        new_text = text + entry
    table_path.write_text(new_text)
    return True
