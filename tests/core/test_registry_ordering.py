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


# --- IC catch-all routing tests ---

def test_mcu_st_routes_to_ic(tmp_path):
    """MCU_ST_STM32F0:STM32F031K6Tx must route to ic (catch-all)."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("MCU_ST_STM32F0:STM32F031K6Tx")
    assert cat is not None
    assert cat.name == "ic", (
        f"Expected ic, got {cat.name!r}. "
        "MCU lib_ids should fall through to the ic catch-all."
    )


def test_ic_does_not_absorb_device_r(tmp_path):
    """IC catch-all must NOT absorb Device:R — resistor category owns it."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:R")
    assert cat is not None
    assert cat.name == "resistor", (
        f"Expected resistor, got {cat.name!r}. "
        "IC catch-all must not absorb Device: prefixed components."
    )


def test_ic_does_not_absorb_device_c(tmp_path):
    """IC catch-all must NOT absorb Device:C — ceramic_cap owns it."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:C")
    assert cat is not None
    assert cat.name == "ceramic_capacitor"


def test_ic_does_not_absorb_device_led(tmp_path):
    """IC catch-all must NOT absorb Device:LED — led category owns it."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:LED")
    assert cat is not None
    assert cat.name == "led"


def test_ic_does_not_absorb_device_crystal(tmp_path):
    """IC catch-all must NOT absorb Device:Crystal — crystal category owns it."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Device:Crystal")
    assert cat is not None
    assert cat.name == "crystal"


def test_connector_not_absorbed_by_ic(tmp_path):
    """Connector lib_ids must not be routed to ic (Connector prefix excluded)."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Connector:Conn_01x02_Pin")
    # Connector category not yet registered → returns None, but NOT ic
    assert cat is None or cat.name != "ic", (
        "IC catch-all must not absorb Connector lib_ids."
    )


def test_jumper_routes_to_ic(tmp_path):
    """Jumper:SolderJumper_2_Open routes to ic (catch-all behavior for non-Device libs)."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("Jumper:SolderJumper_2_Open")
    assert cat is not None
    assert cat.name == "ic", (
        f"Expected ic (catch-all), got {cat.name!r}."
    )


def test_no_colon_lib_id_not_absorbed_by_ic(tmp_path):
    """lib_ids without ':' must not match IC (or any category)."""
    r = default_registry(fp_out_dir=tmp_path / "fp")
    cat = r.lookup("barelib")
    assert cat is None
