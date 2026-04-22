"""Built-in category registration entrypoint."""
from __future__ import annotations
from pathlib import Path


def default_registry(*, fp_out_dir: Path):
    from ..core.registry import Registry
    from . import polarized_cap
    r = Registry()
    r.register(polarized_cap.make(fp_out_dir=fp_out_dir))
    # Additional categories registered in later tasks.
    return r
