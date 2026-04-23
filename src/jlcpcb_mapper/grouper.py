from __future__ import annotations
from dataclasses import dataclass, field
from .io.schematic import SymbolInstance
from .values import normalize_value, category_from_lib_id
from .footprint import package_from_kicad_footprint

@dataclass(frozen=True)
class GroupKey:
    category: str
    value: str
    package_hint: str

@dataclass
class Group:
    key: GroupKey
    instances: list[SymbolInstance] = field(default_factory=list)

def _package_hint(category: str, defaults: dict) -> str:
    d = defaults.get(category, {}) if defaults else {}
    return d.get("package", "")

def group_instances(
    instances: list[SymbolInstance],
    category_defaults: dict,
) -> list[Group]:
    buckets: dict[GroupKey, Group] = {}
    for inst in instances:
        cat = category_from_lib_id(inst.lib_id)
        if cat == "power":
            continue
        val = normalize_value(inst.value, cat)
        # Footprint-derived package hint takes precedence over config default
        pkg = package_from_kicad_footprint(inst.footprint) if inst.footprint else None
        if not pkg:
            pkg = _package_hint(cat, category_defaults)
        key = GroupKey(category=cat, value=val, package_hint=pkg)
        g = buckets.setdefault(key, Group(key=key))
        g.instances.append(inst)
    return list(buckets.values())
