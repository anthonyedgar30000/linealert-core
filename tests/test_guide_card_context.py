from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_guide_card_context_loads_after_guide_control_adapter():
    index = (ROOT / "docs" / "triage" / "index.html").read_text(encoding="utf-8")

    guide_control = index.index("./guide-control-adapter.js")
    guide_context = index.index("./guide-card-context-adapter.js")
    investigation = index.index("./investigation-link-adapter.js")

    assert guide_control < guide_context < investigation


def test_guide_card_context_preserves_observation_restore_and_effect_state():
    script = (ROOT / "docs" / "triage" / "guide-card-context-adapter.js").read_text(
        encoding="utf-8"
    )

    assert "labelerGuideWorkflowContext" in script
    assert "Guide / spacing inspection" in script
    assert "Observed:" in script
    assert "Simulator intervention · guide / spacing restored to reference" in script
    assert "appendFact(box,'OBSERVED',facts.observation)" in script
    assert "appendFact(box,'ACTION','Guide / spacing restored to marked reference')" in script
    assert "appendFact(box,'VERIFY EFFECT',effectState())" in script
    assert "Awaiting fresh 5-container production observation" in script
    assert "Awaiting 5-container trial" in script
    assert "Production verification active" in script


def test_guide_card_context_does_not_replace_opc_owned_machine_state():
    script = (ROOT / "docs" / "triage" / "guide-card-context-adapter.js").read_text(
        encoding="utf-8"
    )

    assert "nodeState" in script
    assert "state.insertAdjacentElement('afterend',box)" in script
    assert "state.textContent" not in script
    assert "nodeState').textContent" not in script
