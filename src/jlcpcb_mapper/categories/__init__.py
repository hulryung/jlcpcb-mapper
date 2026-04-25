"""Built-in category registration entrypoint."""
from __future__ import annotations
from pathlib import Path


def default_registry(*, fp_out_dir: Path) -> Registry:
    # Imports inside the function body to avoid circular dependency:
    # core/registry.py → categories/base.py → categories/__init__.py → core/registry.py
    from ..core.registry import Registry
    from . import polarized_cap, resistor, ceramic_cap, inductor, ferrite_bead, led, crystal, connector, ic
    r = Registry()
    # polarized_cap MUST come before ceramic_cap: LibIdAny(["Device:C"]) in ceramic_cap
    # would match "Device:C_Polarized" via prefix, so polarized_cap must claim it first.
    r.register(polarized_cap.make(fp_out_dir=fp_out_dir))
    r.register(resistor.make(fp_out_dir=fp_out_dir))
    r.register(ceramic_cap.make(fp_out_dir=fp_out_dir))
    r.register(inductor.make(fp_out_dir=fp_out_dir))
    r.register(ferrite_bead.make(fp_out_dir=fp_out_dir))
    r.register(led.make(fp_out_dir=fp_out_dir))
    r.register(crystal.make(fp_out_dir=fp_out_dir))
    r.register(connector.make(fp_out_dir=fp_out_dir))   # BEFORE ic catch-all
    r.register(ic.make(fp_out_dir=fp_out_dir))           # catch-all — MUST be registered LAST
    return r
