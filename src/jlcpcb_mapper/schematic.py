"""Schematic parsing and editing with byte-identical round-trip guarantee.

Uses a text/regex approach to ensure no formatting changes are introduced
when reading and re-writing schematic files. Only targeted mutations are
applied to the in-memory text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Matches instance-level (symbol (lib_id "...") blocks.
# lib_symbols entries use (symbol "name" ...) with a quoted name, not (lib_id ...).
_INSTANCE_TOKEN = re.compile(r'\(symbol\s+\(lib_id\s+"([^"]+)"')

_PROP_RE_TMPL = r'\(property\s+"{name}"\s+"([^"]*)"'


def _match_balanced(text: str, start: int) -> int:
    """Return the index AFTER the matching closing paren for the '(' at text[start]."""
    assert text[start] == "(", f"Expected '(' at {start}, got {text[start]!r}"
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise ValueError("unbalanced parentheses — schematic file may be corrupt")


def _find_lib_symbols_end(text: str) -> int:
    """Return the index AFTER the (lib_symbols ...) block, or 0 if not found."""
    # lib_symbols is a top-level key: `\t(lib_symbols`
    marker = "\t(lib_symbols"
    idx = text.find(marker)
    if idx == -1:
        return 0
    # The '(' of '(lib_symbols' is at idx+1 (the \t is before it)
    open_paren = idx + 1
    assert text[open_paren] == "(", f"Expected '(' at {open_paren}"
    return _match_balanced(text, open_paren)


def _find_instance_blocks(text: str) -> list[tuple[int, int, str]]:
    """Find all (symbol (lib_id ...) ...) instance blocks.

    Skips the (lib_symbols ...) section which contains template definitions.
    Returns list of (start, end_exclusive, lib_id).
    """
    lib_end = _find_lib_symbols_end(text)

    out = []
    i = lib_end
    while True:
        m = _INSTANCE_TOKEN.search(text, i)
        if not m:
            break
        # Walk back to find the opening '(' of '(symbol'
        sym_start = text.rfind("(", 0, m.start() + 1)
        sym_end = _match_balanced(text, sym_start)
        out.append((sym_start, sym_end, m.group(1)))
        i = sym_end
    return out


def _prop_value(block: str, name: str) -> str:
    """Extract a property value from a symbol block string."""
    m = re.search(_PROP_RE_TMPL.format(name=re.escape(name)), block)
    return m.group(1) if m else ""


def _set_or_insert_prop_in_block(block: str, name: str, value: str) -> str:
    """Return a new block string with the named property set to value.

    If the property exists, replaces only its value string. If it does not
    exist, inserts a new property entry before the block's closing paren.
    """
    pattern = _PROP_RE_TMPL.format(name=re.escape(name))
    m = re.search(pattern, block)
    if m:
        # Replace only the captured value group
        return block[: m.start(1)] + value + block[m.end(1) :]
    else:
        # Insert a new property before the last '\n\t)' of the block
        close_idx = block.rfind("\n\t)")
        if close_idx == -1:
            close_idx = len(block) - 1
        insertion = (
            f'\n\t\t(property "{name}" "{value}"\n'
            f"\t\t\t(at 0 0 0)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n"
            f"\t\t)"
        )
        return block[:close_idx] + insertion + block[close_idx:]


@dataclass
class SymbolInstance:
    """Represents a placed schematic symbol instance.

    The _block_start and _block_end attributes are byte offsets into the
    parent Schematic's in-memory text. They are updated automatically after
    each mutation so that subsequent edits remain correct.
    """

    reference: str
    value: str
    lib_id: str
    footprint: str
    lcsc: str
    dnp: bool
    on_board: bool = True
    in_bom: bool = True
    _block_start: int = 0
    _block_end: int = 0


class Schematic:
    """Text-based schematic editor with byte-identical round-trip guarantee.

    Reads the schematic file as raw bytes (UTF-8), stores the decoded text,
    and writes it back as the same bytes. All mutations are done by targeted
    string substitution without reformatting.
    """

    def __init__(self, path: Path, raw: bytes):
        self.path = path
        self._raw = raw  # original bytes preserved for encoding/newline fidelity
        # We work on the decoded string for regex operations
        self._text = raw.decode("utf-8")
        # Live index of instances so we can update offsets after mutations
        self._instances: list[SymbolInstance] = []

    @classmethod
    def load(cls, path: str | Path) -> "Schematic":
        p = Path(path)
        raw = p.read_bytes()
        obj = cls(p, raw)
        return obj

    def save(self, path: str | Path) -> None:
        """Write the (possibly modified) schematic.

        When no edits have been made, the written bytes are byte-identical
        to the original.
        """
        Path(path).write_bytes(self._text.encode("utf-8"))

    def instances(self) -> list[SymbolInstance]:
        """Return all placed symbol instances (excludes lib_symbols templates)."""
        out = []
        for start, end, lib_id in _find_instance_blocks(self._text):
            block = self._text[start:end]
            ref = _prop_value(block, "Reference")
            val = _prop_value(block, "Value")
            fp = _prop_value(block, "Footprint")
            lcsc = _prop_value(block, "LCSC")
            dnp = "(dnp yes)" in block
            on_board = "(on_board no)" not in block
            in_bom = "(in_bom no)" not in block
            inst = SymbolInstance(
                reference=ref or "?",
                value=val or "",
                lib_id=lib_id,
                footprint=fp,
                lcsc=lcsc,
                dnp=dnp,
                on_board=on_board,
                in_bom=in_bom,
                _block_start=start,
                _block_end=end,
            )
            out.append(inst)
        # Cache the live list so mutations can update offsets
        self._instances = out
        return out

    def set_footprint(self, inst: SymbolInstance, value: str) -> None:
        """Set the Footprint property for the given instance."""
        self._mutate_prop(inst, "Footprint", value)
        inst.footprint = value

    def set_lcsc(self, inst: SymbolInstance, value: str) -> None:
        """Set the LCSC property for the given instance."""
        self._mutate_prop(inst, "LCSC", value)
        inst.lcsc = value

    def _mutate_prop(self, inst: SymbolInstance, name: str, value: str) -> None:
        """Apply a property mutation and update all live instance offsets."""
        block = self._text[inst._block_start : inst._block_end]
        new_block = _set_or_insert_prop_in_block(block, name, value)
        delta = len(new_block) - len(block)

        new_text = (
            self._text[: inst._block_start]
            + new_block
            + self._text[inst._block_end :]
        )
        self._text = new_text

        # Capture the boundary BEFORE mutating anything.
        threshold = inst._block_end
        # Update inst's own end.
        inst._block_end += delta
        # Shift any later instances by delta.
        for other in self._instances:
            if other is inst:
                continue
            if other._block_start >= threshold:
                other._block_start += delta
                other._block_end += delta


import os
import shutil as _shutil
from typing import Callable

def atomic_update(path, mutate_fn: "Callable[[Schematic], None]", backup_dir) -> None:
    """Backup then atomically update a schematic file.

    1. Copies the original to backup_dir/<original_name>.
    2. Loads the schematic, applies mutate_fn(sch), writes to .tmp, os.replace.
    """
    path = Path(path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    _shutil.copy2(str(path), str(backup_dir / path.name))
    tmp = path.with_suffix(path.suffix + ".tmp")
    sch = Schematic.load(path)
    mutate_fn(sch)
    sch.save(tmp)
    os.replace(str(tmp), str(path))
