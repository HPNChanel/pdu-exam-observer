from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
STATUS = "M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY"
CURRENT_SUITE_RECEIPT = "M1_R1_SOURCE_SUITE_846_OF_846_PASS"
PROPOSAL_SHA256 = "2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5"
EXECUTABLE_SHA256 = "EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF"
MANIFEST_SHA256 = "9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256"
OLD_EXECUTABLE_SHA256 = "30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27"
OLD_MANIFEST_SHA256 = "071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC"
M2_R0_RECEIPT = "M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED"
GOV_P2_RECEIPT = (
    "GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW"
)
GOV_P2_RESIDUAL = "CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT"
GOV_P3_RECEIPT = (
    "GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_"
    "READY_FOR_INSTITUTIONAL_ROUTING"
)
GOV_P3_RESIDUAL = "ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY"
GOV_P3_MANIFEST_SHA256 = (
    "7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605"
)
GOV_P4_RECEIPT = (
    "GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_"
    "UNCONFIRMED_APPROVAL_NOT_ISSUED"
)
GOV_P4_RESIDUAL = "HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED"
GOV_P4_DEADLINE = "CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION"
GOV_P4_MANIFEST_SHA256 = (
    "f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531"
)
GOV_P5_RECEIPT = (
    "GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_"
    "PENDING_HUMAN_RESPONSE_NOT_SUBMITTED"
)
GOV_P5_MANIFEST_SHA256 = (
    "4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8"
)
GOV_P5_LATE_BLOCKER = "CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED"
GOV_P5_ETHICS_BLOCKER = "HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED"
GOV_P5_RESIDUAL = "HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED"
M2_STATIC_BINDINGS_DIGEST = (
    "5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979"
)
M2_CANDIDATE_SHA256 = (
    "cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb"
)
M2_SCHEMA_SHA256 = (
    "1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca"
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _section(document: str, heading: str) -> str:
    start = document.index(heading)
    next_heading = document.find("\n## ", start + len(heading))
    return document[start:] if next_heading == -1 else document[start:next_heading]


def test_current_m1_r1_evidence_tuple_is_consistent() -> None:
    ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M1-R1"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G9"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G5"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "verification": _read("docs/ai/M1_R1_VERIFICATION.md"),
    }

    for name, ledger in ledgers.items():
        assert STATUS in ledger, name
        assert CURRENT_SUITE_RECEIPT in ledger, name
        assert EXECUTABLE_SHA256 in ledger, name
        assert MANIFEST_SHA256 in ledger, name
        assert "186" in ledger, name
        assert "843/843" in ledger, name
        assert "846/846" in ledger, name
        assert "58/58" in ledger, name
        assert "8/8" in ledger, name
        assert "Earlier two full invocations" in ledger, name
        assert "The package was not rebuilt" in ledger, name
        assert "no clean" not in ledger.lower(), name

    gov_p2_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## GOV-P2"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G11"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G7"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
        "risk": _read("docs/plans/RISK_REGISTER.md"),
    }
    for name, ledger in gov_p2_ledgers.items():
        assert GOV_P2_RECEIPT in ledger, name
        assert GOV_P2_RESIDUAL in ledger, name
        assert "NOT_SUBMITTED" in ledger, name
        assert "PENDING_EXTERNAL_REVIEW" in ledger, name

    gov_p3_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## GOV-P3"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G12"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G8"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    for name, ledger in gov_p3_ledgers.items():
        assert GOV_P3_RECEIPT in ledger, name
        assert GOV_P3_RESIDUAL in ledger, name
        assert GOV_P3_MANIFEST_SHA256 in ledger, name
        assert "USER_STATED_UNVERIFIED" in ledger, name
        assert "READY_FOR_INSTITUTIONAL_ROUTING" in ledger, name
        assert "institutional_approval_status=NOT_ISSUED" in ledger, name
        assert "submission_state=NOT_SUBMITTED" in ledger, name

    risk = _read("docs/plans/RISK_REGISTER.md")
    assert GOV_P3_RECEIPT in risk
    assert GOV_P3_RESIDUAL in risk
    assert "ADV-02=PENDING_EXTERNAL_DECISION" in risk

    gov_p4_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## GOV-P4"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G13"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G9"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    for name, ledger in gov_p4_ledgers.items():
        assert GOV_P4_RECEIPT in ledger, name
        assert GOV_P4_RESIDUAL in ledger, name
        assert GOV_P4_DEADLINE in ledger, name
        assert GOV_P4_MANIFEST_SHA256 in ledger, name
        assert "adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES" in ledger, name
        assert "SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED" in ledger, name
        assert "institutional_approval_status=NOT_ISSUED" in ledger, name
        assert "submission_state=NOT_SUBMITTED" in ledger, name

    assert GOV_P4_RECEIPT in risk
    assert GOV_P4_RESIDUAL in risk
    assert GOV_P4_DEADLINE in risk

    gov_p5_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## GOV-P5A"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G14"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G10"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    for name, ledger in gov_p5_ledgers.items():
        assert GOV_P5_RECEIPT in ledger, name
        assert GOV_P5_MANIFEST_SHA256 in ledger, name
        assert GOV_P5_LATE_BLOCKER in ledger, name
        assert GOV_P5_ETHICS_BLOCKER in ledger, name
        assert GOV_P5_RESIDUAL in ledger, name
        assert "HC-01" in ledger, name
        assert "HC-02" in ledger, name
        assert "FACULTY_ADVISOR_FIRST" in ledger, name
        assert "human_response_status=PENDING" in ledger, name
        assert "external_transmission_authorized=false" in ledger, name
        assert "submission_state=NOT_SUBMITTED" in ledger, name

    assert GOV_P5_RECEIPT in risk
    assert GOV_P5_LATE_BLOCKER in risk
    assert GOV_P5_ETHICS_BLOCKER in risk
    assert GOV_P5_RESIDUAL in risk


def test_historical_milestones_are_not_presented_as_current() -> None:
    roadmap = _read("docs/plans/ROADMAP.md")
    acceptance = _read("docs/plans/ACCEPTANCE_GATES.md")
    quality = _read("docs/ai/QUALITY_GATES.md")

    historical_sections = (
        _section(roadmap, "## M0"),
        _section(roadmap, "## M1 -"),
        _section(roadmap, "## GOV-P1"),
        _section(acceptance, "## G1"),
        _section(quality, "## G3"),
    )
    assert all("HISTORICAL" in section for section in historical_sections)
    assert any(OLD_EXECUTABLE_SHA256 in section for section in historical_sections)
    assert any(OLD_MANIFEST_SHA256 in section for section in historical_sections)

    current_sections = (
        _section(roadmap, "## M1-R1"),
        _section(acceptance, "## G9"),
        _section(quality, "## G5"),
    )
    assert all(OLD_EXECUTABLE_SHA256 not in section for section in current_sections)
    assert all(OLD_MANIFEST_SHA256 not in section for section in current_sections)
    assert "superseded by M1-R1" in _section(roadmap, "## GOV-P1")
    assert "HISTORICAL" in _section(roadmap, "## GOV-P1")
    gov_p2_heading = _section(roadmap, "## GOV-P2").splitlines()[0]
    assert "(HISTORICAL)" not in gov_p2_heading
    gov_p3_heading = _section(roadmap, "## GOV-P3").splitlines()[0]
    assert "(HISTORICAL)" not in gov_p3_heading
    gov_p4_heading = _section(roadmap, "## GOV-P4").splitlines()[0]
    assert "(HISTORICAL)" not in gov_p4_heading
    gov_p5_heading = _section(roadmap, "## GOV-P5A").splitlines()[0]
    assert "(HISTORICAL)" not in gov_p5_heading


def test_authority_ceiling_and_m2_boundary_remain_closed() -> None:
    roadmap = _read("docs/plans/ROADMAP.md")
    current_ledgers = {
        "roadmap": _section(roadmap, "## M1-R1"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G9"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G5"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "verification": _read("docs/ai/M1_R1_VERIFICATION.md"),
    }
    bindings = (
        "production_reconciler_implemented=false",
        "production_reconciler_real_storage_verified=false",
        "real_data_deletion_authorized=false",
        "participant_collection_authorized=false",
        "research_ready=false",
        "collection_authorized=false",
        "authority_status=AUTHORITY_NOT_ISSUED",
    )
    for name, ledger in current_ledgers.items():
        for binding in bindings:
            assert binding in ledger, f"{name}: {binding}"

    governed = "\n".join(current_ledgers.values())
    for binding in bindings:
        if binding.endswith("=false"):
            assert f"{binding.removesuffix('=false')}=true" not in governed

    assert "Status: unopened" in _section(roadmap, "## M2")
    assert PROPOSAL_SHA256 in governed

    gov_p5_ledgers = {
        "roadmap": _section(roadmap, "## GOV-P5A"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G14"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G10"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    gov_p5_bindings = (
        "production_reconciler_implemented=false",
        "production_reconciler_real_storage_verified=false",
        "real_data_deletion_authorized=false",
        "execution_authorized=false",
        "physical_camera_access_authorized=false",
        "device_gate_decision=UNVERIFIED",
        "d1_go=false",
        "participant_collection_authorized=false",
        "research_ready=false",
        "collection_authorized=false",
        "authority_status=AUTHORITY_NOT_ISSUED",
    )
    for name, ledger in gov_p5_ledgers.items():
        for binding in gov_p5_bindings:
            assert binding in ledger, f"{name}: {binding}"
    current_gov_p5 = "\n".join(gov_p5_ledgers.values())
    forbidden_current_claims = (
        "human_response_status=RECEIVED",
        "submission_state=SUBMITTED",
        "external_transmission_authorized=true",
        "institutional_approval_status=ISSUED",
        "research_ready=true",
        "collection_authorized=true",
        "participant_collection_authorized=true",
        "authority_status=ISSUED",
    )
    for forbidden in forbidden_current_claims:
        assert forbidden not in current_gov_p5

    candidate_path = ROOT / "docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json"
    schema_path = ROOT / "docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json"
    candidate_bytes = candidate_path.read_bytes()
    candidate = json.loads(candidate_bytes)
    static_bindings_bytes = json.dumps(
        candidate["static_bindings"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    artifacts = candidate["static_bindings"]["artifacts"]

    assert hashlib.sha256(static_bindings_bytes).hexdigest() == (
        M2_STATIC_BINDINGS_DIGEST
    )
    assert hashlib.sha256(candidate_bytes).hexdigest() == M2_CANDIDATE_SHA256
    assert hashlib.sha256(schema_path.read_bytes()).hexdigest() == M2_SCHEMA_SHA256
    assert len(artifacts["source_inventory"]) == 24
    assert set(artifacts) - {"source_inventory"} == {
        "uv_lock",
        "pose_landmarker_lite_task",
        "blaze_face_short_range_tflite",
    }
    assert len(candidate["static_bindings"]["policy_preimages"]) == 21

    contract = _read("docs/ai/M2_D1_N2_AUTHORITY_CONTRACT.md")
    current_contract = contract.split(
        "### HISTORICAL_SUPERSEDED_NON_AUTHORIZING", maxsplit=1
    )[0]
    m2_ledgers = {
        "authority_contract": current_contract,
        "readiness_pack": _read("docs/spec/M2_D1_N2_READINESS_PACK.md"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "roadmap": _section(roadmap, "## M2"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G10"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G6"),
        "receipt": _read("docs/ai/M2_R0_AUTHORITY_REENTRY_RECEIPT.md"),
    }
    for name, ledger in m2_ledgers.items():
        assert M2_R0_RECEIPT in ledger, name
        assert M2_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_CANDIDATE_SHA256 in ledger, name
        assert M2_SCHEMA_SHA256 in ledger, name

    assert "49d877e2dbd85368e5ec0feb1a4207a0ca6926840bfa7ffaf6d39875aaf2a208" not in (
        current_contract
    )
    assert "15 fixed artifacts" not in current_contract
    assert "14 explicit policy preimages" not in current_contract

    receipt = m2_ledgers["receipt"]
    for binding in (
        "bootstrap_provisioning_status=UNPROVISIONED",
        "fresh_a0_status=NOT_ISSUED",
        "a1_status=NOT_OPENED",
        "x0_status=BLOCKED",
        "physical_camera_access_authorized=false",
        "authority_status=AUTHORITY_NOT_ISSUED",
    ):
        assert binding in receipt

    gov_p2_ledgers = {
        "roadmap": _section(roadmap, "## GOV-P2"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G11"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G7"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    gov_p2_bindings = (
        "production_reconciler_implemented=false",
        "production_reconciler_real_storage_verified=false",
        "real_data_deletion_authorized=false",
        "execution_authorized=false",
        "physical_camera_access_authorized=false",
        "device_gate_decision=UNVERIFIED",
        "d1_go=false",
        "participant_collection_authorized=false",
        "research_ready=false",
        "collection_authorized=false",
        "authority_status=AUTHORITY_NOT_ISSUED",
    )
    for name, ledger in gov_p2_ledgers.items():
        for binding in gov_p2_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "institutional_approval_status=ISSUED" not in ledger, name
        assert "submission_state=SUBMITTED" not in ledger, name

    gov_p3_ledgers = {
        "roadmap": _section(roadmap, "## GOV-P3"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G12"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G8"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    for name, ledger in gov_p3_ledgers.items():
        for binding in gov_p2_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "institutional_approval_status=ISSUED" not in ledger, name
        assert "submission_state=SUBMITTED" not in ledger, name
        assert "ADVISOR_REVIEW_NOT_COMPLETED" not in ledger, name

    gov_p4_ledgers = {
        "roadmap": _section(roadmap, "## GOV-P4"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G13"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G9"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "pre_collection": _read("docs/spec/PRE_COLLECTION_GOVERNANCE.md"),
    }
    for name, ledger in gov_p4_ledgers.items():
        for binding in gov_p2_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "institutional_approval_status=ISSUED" not in ledger, name
        assert "submission_state=SUBMITTED" not in ledger, name
        assert "human_subjects_review_requirement=NOT_REQUIRED" not in ledger, name
