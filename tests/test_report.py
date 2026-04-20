from jlcpcb_mapper.report import RunReport

def test_report_counts_and_json_serializable():
    r = RunReport()
    r.schematics = ["a.kicad_sch"]
    r.total_empty_instances = 10
    r.filtered_in = 8
    r.add_group_result(
        group_label="resistor 0Ω 0402",
        refs=["R1","R2"],
        lcsc="C17168",
        footprint="Resistor_SMD:R_0402_1005Metric",
        downloaded=False,
        source="llm",
    )
    r.add_failure(kind="no_candidates", detail="connector ... no DB match")
    data = r.to_dict()
    assert data["total_empty_instances"] == 10
    assert data["groups"][0]["lcsc"] == "C17168"
    assert len(data["failures"]) == 1
    text = r.to_text()
    assert "Groups: 1" in text

def test_write_json_creates_file(tmp_path):
    r = RunReport()
    r.total_empty_instances = 3
    out = tmp_path / "sub" / "run.json"
    r.write_json(out)
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert data["total_empty_instances"] == 3
