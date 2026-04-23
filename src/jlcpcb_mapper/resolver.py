from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .kicad_fp import match_kicad_footprint
from .io.easyeda import download_footprint
from .io.parts_db import PartRow

@dataclass
class ResolveResult:
    footprint: str
    downloaded: bool
    download_failed: bool = False

def resolve_footprint(
    category: str,
    part: PartRow,
    out_dir: Path,
    overrides: dict[str, str],
) -> ResolveResult:
    # Try KiCad built-in first
    fp = match_kicad_footprint(category, part.package, overrides)
    if fp:
        return ResolveResult(footprint=fp, downloaded=False)
    # Fallback: download from EasyEDA/JLCPCB
    path = download_footprint(part.lcsc, out_dir)
    if path is None:
        return ResolveResult(footprint="", downloaded=False, download_failed=True)
    lib_name = "LCSC"
    fp_name = path.stem  # "C12345_QFN"
    return ResolveResult(footprint=f"{lib_name}:{fp_name}", downloaded=True)
