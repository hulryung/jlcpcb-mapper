from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .schematic import Schematic, SymbolInstance
from .values import category_from_lib_id

@dataclass
class Target:
    sch_path: Path
    inst: SymbolInstance

@dataclass
class Project:
    root: Path
    schematics: list[Path]
    loaded: dict[Path, Schematic]  # NOTE: public (no underscore) so callers can retrieve Schematic objs

def load_project(kicad_pro) -> Project:
    kicad_pro = Path(kicad_pro)
    project_dir = kicad_pro.parent
    schematics = sorted(project_dir.glob("*.kicad_sch"))
    loaded = {p: Schematic.load(p) for p in schematics}
    return Project(root=project_dir, schematics=schematics, loaded=loaded)

def select_targets(
    proj: Project,
    *,
    fill_lcsc_only: bool,
    include_dnp: bool,
) -> list[Target]:
    out: list[Target] = []
    for sch_path in proj.schematics:
        sch = proj.loaded[sch_path]
        for inst in sch.instances():
            if category_from_lib_id(inst.lib_id) == "power":
                continue
            if inst.dnp and not include_dnp:
                continue
            if not inst.value:
                continue
            if fill_lcsc_only:
                if inst.lcsc == "":
                    out.append(Target(sch_path, inst))
            else:
                if inst.footprint == "" and inst.lcsc == "":
                    out.append(Target(sch_path, inst))
    return out
