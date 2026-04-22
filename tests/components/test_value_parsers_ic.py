"""Tests for ICValueParser."""
import pytest
from jlcpcb_mapper.components.value_parsers import ICValueParser
from jlcpcb_mapper.categories.spec.ic import ICSpec


@pytest.fixture
def parser():
    return ICValueParser()


def test_plain_mpn(parser):
    result = parser.parse("STM32F031K6T6")
    assert result == ICSpec(mpn="STM32F031K6T6")


def test_trimmed(parser):
    result = parser.parse("  AO3400A  ")
    assert result == ICSpec(mpn="AO3400A")


def test_empty_returns_none(parser):
    assert parser.parse("") is None


def test_whitespace_only_returns_none(parser):
    assert parser.parse("   ") is None


def test_case_preserved(parser):
    """MPNs are case-sensitive; lowercase letters should not be altered."""
    result = parser.parse("LM2596S-3.3")
    assert result == ICSpec(mpn="LM2596S-3.3")


def test_lowercase_preserved(parser):
    """All-lowercase MPN is kept as-is."""
    result = parser.parse("ao3400a")
    assert result == ICSpec(mpn="ao3400a")


def test_mixed_case_preserved(parser):
    result = parser.parse("ESP32-S3-WROOM-1")
    assert result == ICSpec(mpn="ESP32-S3-WROOM-1")
