from jlcpcb_mapper.observability.trace import Trace, TraceEvent

def test_record_appends_event():
    t = Trace()
    t.record("match", lib_id="Device:CP", category="polarized_capacitor")
    assert len(t.events) == 1
    e = t.events[0]
    assert e.stage == "match"
    assert e.data == {"lib_id": "Device:CP", "category": "polarized_capacitor"}
    assert isinstance(e.timestamp_ms, int)

def test_skip_uses_skip_stage():
    t = Trace()
    t.skip("no category for lib_id", "Device:Unknown")
    assert t.events[0].stage == "skip"
    assert t.events[0].data["reason"] == "no category for lib_id"
    assert t.events[0].data["args"] == ("Device:Unknown",)

def test_events_are_ordered():
    t = Trace()
    t.record("a"); t.record("b"); t.record("c")
    assert [e.stage for e in t.events] == ["a", "b", "c"]
