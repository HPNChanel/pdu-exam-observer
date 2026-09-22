import pytest

from pdu_exam_observer.research_runtime.rules import RulePolicy, TemporalRuleEngine


def test_persistence_hysteresis_merge_and_cooldown() -> None:
    engine = TemporalRuleEngine(RulePolicy.demo())
    assert engine.advance(0, 1, 30.0, 0, quality_ok=True) == []
    assert engine.advance(1999, 1, 30.0, 0, quality_ok=True) == []
    onset = engine.advance(2000, 1, 30.0, 0, quality_ok=True)
    assert len(onset) == 1 and onset[0].kind == "START"
    assert onset[0].start_ms == 0 and onset[0].eligible_onset_ms == 2000
    logical_id = onset[0].logical_id
    # Between on/off thresholds sustains the same event.
    engine.advance(2300, 1, 10.0, 0, quality_ok=True)
    assert engine.advance(2400, 1, 0, 0, quality_ok=True) == []
    resumed = engine.advance(2700, 1, 30.0, 0, quality_ok=True)
    assert all(e.logical_id == logical_id for e in resumed)
    engine.advance(2800, 1, 0, 0, quality_ok=True)
    ended = engine.advance(3601, 1, 0, 0, quality_ok=True)
    assert ended[-1].kind == "END" and ended[-1].logical_id == logical_id
    assert engine.advance(3700, 1, 30.0, 0, quality_ok=True) == []


def test_presence_persists_and_quality_failure_never_becomes_normal() -> None:
    engine = TemporalRuleEngine(RulePolicy.demo())
    engine.advance(0, 0, 0, 0, quality_ok=True)
    assert engine.advance(500, 0, 0, 0, quality_ok=True) == []
    events = engine.advance(1500, 0, 0, 0, quality_ok=True)
    assert events[0].label == "NO_PERSON"
    engine.advance(1600, 1, 0, 0, quality_ok=False)
    assert engine.operator_outcome == "TECHNICAL_INSUFFICIENT"
    with pytest.raises(ValueError, match="TIMESTAMP"):
        engine.advance(1500, 1, 0, 0, quality_ok=True)


def test_research_policy_cannot_use_unselected_demo_thresholds() -> None:
    doc = RulePolicy.demo().to_document()
    with pytest.raises(ValueError, match="POLICY_NOT_FROZEN"):
        RulePolicy.from_document(doc, research=True)
    doc.update(status="FROZEN", selection_source="CALIBRATION")
    assert RulePolicy.from_document(doc, research=True).status == "FROZEN"
    doc["head_down_off"] = doc["head_down_on"] + 1
    with pytest.raises(ValueError):
        RulePolicy.from_document(doc, research=True)
