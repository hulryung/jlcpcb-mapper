"""Footprint resolvers. BuiltinMap and EasyedaFallback compose via Composite."""
from __future__ import annotations
from pathlib import Path
from ..categories.base import ResolveResult
from ..parts_db import PartRow


class BuiltinMap:
    """package_hint -> KiCad library footprint id."""

    def __init__(self, mapping: dict[str, str]):
        self._map = dict(mapping)

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        fp = self._map.get(package_hint, "")
        return ResolveResult(footprint=fp, downloaded=False)


class EasyedaFallback:
    """Download a KiCad footprint from EasyEDA for the given LCSC."""

    def __init__(self, out_dir: Path, downloader=None):
        self.out_dir = Path(out_dir)
        # Injectable downloader for tests; defaults to production downloader.
        if downloader is None:
            from ..downloader import download_footprint as _dl
            downloader = _dl
        self._download = downloader

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        path = self._download(part.lcsc, self.out_dir)
        if path is None:
            return ResolveResult(footprint="", downloaded=False, download_failed=True)
        fp_name = Path(path).stem
        return ResolveResult(footprint=f"LCSC:{fp_name}", downloaded=True)


class Composite:
    """Try each resolver in order; return the first non-empty footprint."""

    def __init__(self, resolvers: list):
        self._resolvers = list(resolvers)

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        last = ResolveResult(footprint="", downloaded=False)
        for r in self._resolvers:
            res = r.resolve(part, package_hint)
            if res.footprint:
                return res
            last = res
        return last
