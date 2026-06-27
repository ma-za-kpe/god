"""Avatar persona/use-case acceptance suite tests."""

from __future__ import annotations

from avatar import (
    ACCEPTANCE_CASES,
    REQUIRED_FAILURE_USE_CASES,
    REQUIRED_PERSONAS,
    REQUIRED_USE_CASES,
    AcceptanceCase,
    AcceptanceMode,
    build_acceptance_suite_report,
    validate_acceptance_suite,
)


def test_acceptance_suite_covers_all_required_personas_and_use_cases():
    report = build_acceptance_suite_report()

    assert report["status"] == "complete"
    assert set(report["personas"]) == REQUIRED_PERSONAS
    assert REQUIRED_USE_CASES <= set(report["use_cases"])
    assert REQUIRED_FAILURE_USE_CASES <= set(report["failure_use_cases"])
    assert report["validation_gaps"] == []
    assert report["audit_link"].startswith("docs/90-fish-comfyui-integration-audit.md")


def test_each_persona_has_automated_or_manual_acceptance_path():
    by_persona = {persona: [] for persona in REQUIRED_PERSONAS}
    for case in ACCEPTANCE_CASES:
        by_persona[case.persona].append(case)

    for persona, cases in by_persona.items():
        assert cases, persona
        assert any(case.automated_tests or case.manual_vod_checklist for case in cases), persona


def test_failure_paths_include_fish_comfy_queue_and_observer_switching():
    failure_cases = {case.use_case: case for case in ACCEPTANCE_CASES if case.failure_path}

    for use_case in REQUIRED_FAILURE_USE_CASES:
        case = failure_cases[use_case]
        assert case.required_evidence
        assert case.automated_tests or case.manual_vod_checklist


def test_operator_case_exposes_health_fallback_queue_and_visual_source():
    report = build_acceptance_suite_report()
    operator_cases = [case for case in report["cases"] if case["persona"] == "operator"]
    combined = " ".join(
        " ".join(case["success_criteria"] + case["required_evidence"]) for case in operator_cases
    )

    assert "voice" in combined or "Fish" in combined
    assert "fallback" in combined
    assert "queue" in combined
    assert "visual" in combined


def test_validation_reports_missing_persona_and_missing_evidence_path():
    incomplete = (
        AcceptanceCase(
            case_id="incomplete",
            persona="live_speaker",
            use_case="agent_speaks_normally",
            modes=(AcceptanceMode.AUTOMATED,),
            success_criteria=("A line plays.",),
        ),
    )

    gaps = validate_acceptance_suite(incomplete)

    assert "missing_persona:operator" in gaps
    assert "missing_use_case:agent_listens_silently_30s" in gaps
    assert "missing_failure_path:fish_failure_degrades_gracefully" in gaps
    assert "missing_evidence_path:incomplete" in gaps
