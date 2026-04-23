"""Tests for ICPromptHook."""
import pytest
from jlcpcb_mapper.components.prompt_hooks import ICPromptHook
from jlcpcb_mapper.io.parts_db import PartRow


def _row():
    return PartRow(
        lcsc="C123456", category="Microcontroller", mfr="ST",
        mfr_part="STM32F031K6T6", package="LQFP-32",
        description="ARM Cortex-M0 MCU 32KB Flash",
        basic=1, preferred=0, stock=10000, price=1.20,
    )


def test_selection_criteria_mentions_mpn():
    h = ICPromptHook()
    criteria = h.selection_criteria()
    assert "MPN" in criteria


def test_selection_criteria_mentions_exactly():
    h = ICPromptHook()
    criteria = h.selection_criteria()
    assert "exactly" in criteria.lower()


def test_selection_criteria_is_deterministic():
    h = ICPromptHook()
    assert h.selection_criteria() == h.selection_criteria()


def test_candidate_payload_9_keys():
    h = ICPromptHook()
    payload = h.candidate_payload(_row())
    expected_keys = {"lcsc", "mfr", "mfr_part", "package", "basic", "preferred",
                     "stock", "price", "description"}
    assert set(payload.keys()) == expected_keys


def test_candidate_payload_values():
    h = ICPromptHook()
    payload = h.candidate_payload(_row())
    assert payload["lcsc"] == "C123456"
    assert payload["mfr_part"] == "STM32F031K6T6"
    assert payload["package"] == "LQFP-32"
    assert payload["basic"] is True
    assert payload["preferred"] is False
    assert payload["stock"] == 10000


def test_candidate_payload_description_truncated():
    """Description is truncated at 200 chars."""
    long_desc = "A" * 300
    row = PartRow(
        lcsc="C1", category="IC", mfr="X", mfr_part="Y",
        package="SOIC-8", description=long_desc,
        basic=0, preferred=0, stock=100, price=0.10,
    )
    h = ICPromptHook()
    payload = h.candidate_payload(row)
    assert len(payload["description"]) == 200
