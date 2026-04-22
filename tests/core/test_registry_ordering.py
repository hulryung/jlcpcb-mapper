"""Test that the default_registry ordering correctly routes Device:C_Polarized to
polarized_capacitor and not ceramic_capacitor.

This is a regression guard: CeramicCap uses LibIdAny(["Device:C"]) which matches
any lib_id equal to "Device:C" or starting with "Device:C_". Since "Device:C_Polarized"
starts with "Device:C_", ceramic_cap would claim it if registered first. The registry
must register polarized_cap before ceramic_cap to prevent this.
"""
from pathlib import Path
from jlcpcb_mapper.categories import default_registry


def test_device_c_polarized_routes_to_polarized_cap(tmp_path):
    """Device:C_Polarized must match polarized_capacitor, not ceramic_capacitor."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:C_Polarized")
    assert cat is not None
    assert cat.name == "polarized_capacitor", (
        f"Expected polarized_capacitor, got {cat.name!r}. "
        "Check registry ordering in categories/__init__.py."
    )


def test_device_c_routes_to_ceramic_cap(tmp_path):
    """Device:C must match ceramic_capacitor."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:C")
    assert cat is not None
    assert cat.name == "ceramic_capacitor", (
        f"Expected ceramic_capacitor, got {cat.name!r}."
    )


def test_device_c_small_routes_to_ceramic_cap(tmp_path):
    """Device:C_Small (prefix of Device:C) must match ceramic_capacitor."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:C_Small")
    assert cat is not None
    assert cat.name == "ceramic_capacitor", (
        f"Expected ceramic_capacitor, got {cat.name!r}."
    )


def test_device_cp_routes_to_polarized_cap(tmp_path):
    """Device:CP must still route to polarized_capacitor."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:CP")
    assert cat is not None
    assert cat.name == "polarized_capacitor"
