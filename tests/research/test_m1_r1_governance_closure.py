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
M2_S2A_RECEIPT = (
    "M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
M2_S2A_STATIC_BINDINGS_DIGEST = (
    "84694c545120b69cebaa8d64fb40c3c1d574afcecd69126f1238d5e285a7a22f"
)
M2_S2A_CANDIDATE_SHA256 = (
    "cd89fad5be9e804fcdf56b87f8edd517fe15be74de0e1c0dcd01d0e10bb16bec"
)
M2_S2A_SCHEMA_SHA256 = (
    "fcc3ae40caf53e2afd3f67b1f0739ce863e4a6780673e6de0afd904750571d94"
)
M2_S2B_RECEIPT = (
    "M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
M2_S2B_STATIC_BINDINGS_DIGEST = (
    "6e84eb0699658c61efd335a175a2abb4470f37afeaff131d94cdce332640fa43"
)
M2_S2B_CANDIDATE_SHA256 = (
    "99365851f4fbad6f78c9b94c30eaef362b281c1a901cc15b40f2c5707e9fd771"
)
M2_S2B_SCHEMA_SHA256 = (
    "1bec3a9e9747136f01e43dd76de62f5b622eb00540714ee4c1639ee470edcb2d"
)
M2_S2C_RECEIPT = (
    "M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
M2_S2C_STATIC_BINDINGS_DIGEST = (
    "d54ec5277d9713128e03a0eaae787c5ff6fd04ee6e48fee3654f87655d847248"
)
M2_S2C_CANDIDATE_SHA256 = (
    "582bb50f0ca2118937f7d79d7dd8a0bff3d43d72a58ae540c27c41ccddcabd71"
)
M2_S2C_SCHEMA_SHA256 = (
    "9c460d3fb874faea444ab97a3c85bc70c37d25f6ea1ced5be4f2dbec20092387"
)
M2_S2D_RECEIPT = (
    "M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
M2_S2D_STATIC_BINDINGS_DIGEST = (
    "7204b1d53dbac8d5fd7f057c9b5a63e3fde10ec4c68111e4fa2b0ef9312880d3"
)
M2_S2D_CANDIDATE_SHA256 = (
    "46221d85c38df2e44b62d688ff5a162519f215078462ef6f54bc47b65c75abd0"
)
M2_S2D_SCHEMA_SHA256 = (
    "23d742592c018343767ff8b670e1a253f7e2e2cbdf1a91c4829e8dc7bf30a9d3"
)
M2_S2E_RECEIPT = (
    "M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
M2_S2E_STATIC_BINDINGS_DIGEST = (
    "38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585"
)
M2_S2E_CANDIDATE_SHA256 = (
    "15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119"
)
M2_S2E_SCHEMA_SHA256 = (
    "abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5"
)
M2_S3A_RECEIPT = (
    "M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_"
    "REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY"
)
M2_S3A_STATIC_BINDINGS_DIGEST = (
    "e11984ea6cd5146a862b9065a22063cf80d3eb8aa7ce92b6929450cafa7769d5"
)
M2_S3A_CANDIDATE_SHA256 = (
    "d98a0013e4c4b3c219fcd0d53e66c5c99dcd3c4fcea6d823d54bf1e040e0c258"
)
M2_S3A_SCHEMA_SHA256 = (
    "17cb07cb672dfccc0c5fe0c3fffd91a82e63a392bbbc0660d09b047dce8ad5f1"
)
M2_S3A_AUDIT_SHA256 = (
    "a63c0fefa7c7aba37685ccb65bec7fd605448e42873d5d8252975a82ea9269e5"
)
M2_S3B_RECEIPT = (
    "M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_"
    "INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY"
)
M2_S3B_STATIC_BINDINGS_DIGEST = (
    "a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f"
)
M2_S3B_CANDIDATE_SHA256 = (
    "a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639"
)
M2_S3B_SCHEMA_SHA256 = (
    "3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca"
)
M2_S3B_RECEIPT_SHA256 = (
    "bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd"
)
M2_S3C_RECEIPT = (
    "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_"
    "SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
M2_S3C_STATIC_BINDINGS_DIGEST = (
    "721783d4d89eb55a599a1505574741d9e631d66a5ceee7e443f4469058104a8a"
)
M2_S3C_CANDIDATE_SHA256 = (
    "ca5e80e847e11f93f8a8da33ddc743b1f106a50af864a7eb339194a1ef86929a"
)
M2_S3C_SCHEMA_SHA256 = (
    "3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca"
)
M2_S3C_RECEIPT_SHA256 = (
    "479aa2e364216a8f4560fbf98a31a6935829d847dfbace65f7c66fae8778bbb7"
)
M2_S3D_RECEIPT = (
    "M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_"
    "SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
M2_S3D_STATIC_BINDINGS_DIGEST = (
    "034eb3e19f88377529f5ffc37c077938b42563a447d1d6e6a481c1b635cbf607"
)
M2_S3D_CANDIDATE_SHA256 = (
    "ced85d39533de902da652c4a7f56ea85eaf4891a5d8b27946badf8aebcae5c79"
)
M2_S3D_SCHEMA_SHA256 = (
    "7125de572f5a78b986a768b484315b818e1c630d10ada48ea31bd0915c300058"
)
M2_S3D_RECEIPT_SHA256 = (
    "4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed"
)
M2_S3E_A_RECEIPT = (
    "M2_S3E_A_SAME_HOST_ISOLATED_PORTABILITY_LOCALLY_VERIFIED_"
    "CLEAN_ENVIRONMENT_HANDOFF_READY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
M2_S3E_A_STATIC_BINDINGS_DIGEST = (
    "ca925c67903757b776fceff0f785eb46fe2a74f8a1fd18681da4a6ff7dea212b"
)
M2_S3E_A_CANDIDATE_SHA256 = (
    "dfbea5e5cb6bfa93fc33e3ed7225b25b43ba92091729f026dc116b7fbd8d2f83"
)
M2_S3E_A_SCHEMA_SHA256 = (
    "302dc8156c0da4bee47b39f0c42d2cc91b09ea0bb3eeb49853413d52bff30003"
)
M2_S3E_A_RECEIPT_SHA256 = (
    "e952c3364be3513dc2decd7d2ff55d9328d91b1e6a629b51b30d55419ce73b85"
)
# Current source binding was refreshed for the approved workspace implementation.
# The S3E constants above remain pinned to the immutable historical receipt.
WORKSPACE_STATIC_BINDINGS_DIGEST = (
    "167dc3dd03b60b8c44cbdec47b7050b1531a350b0f7bf647a3aac578f4223395"
)
WORKSPACE_CANDIDATE_SHA256 = (
    "25fd492678a2d4a4d9f1b5220e8cfc8a0846c73f183f1ebda9b5c6dc19fb5ecc"
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

    m2_s2a_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S2A"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G15"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G11"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "risk": _read("docs/plans/RISK_REGISTER.md"),
    }
    for name, ledger in m2_s2a_ledgers.items():
        assert M2_S2A_RECEIPT in ledger, name
        assert M2_S2A_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S2A_CANDIDATE_SHA256 in ledger, name
        assert M2_S2A_SCHEMA_SHA256 in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name

    m2_s2b_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S2B"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G16"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G12"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "risk": risk,
    }
    for name, ledger in m2_s2b_ledgers.items():
        assert M2_S2B_RECEIPT in ledger, name
        assert M2_S2B_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S2B_CANDIDATE_SHA256 in ledger, name
        assert M2_S2B_SCHEMA_SHA256 in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "run_kind=NOMINAL_20M" in ledger, name
        assert "18077" in ledger or "18,077" in ledger, name
        assert "package_contains_integration=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name

    m2_s2c_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S2C"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G17"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G13"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "risk": risk,
    }
    for name, ledger in m2_s2c_ledgers.items():
        assert M2_S2C_RECEIPT in ledger, name
        assert M2_S2C_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S2C_CANDIDATE_SHA256 in ledger, name
        assert M2_S2C_SCHEMA_SHA256 in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "package_contains_integration=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name

    m2_s3c_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S3C"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G22"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G18"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3C outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3C packaged synthetic runtime smoke boundary",
        ),
        "verification": _read("docs/ai/M2_S3C_VERIFICATION.md"),
        "risk": risk,
    }
    for name, ledger in m2_s3c_ledgers.items():
        assert M2_S3C_RECEIPT in ledger, name
        assert M2_S3C_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S3C_CANDIDATE_SHA256 in ledger, name
        assert M2_S3C_SCHEMA_SHA256 in ledger, name
        assert M2_S3C_RECEIPT_SHA256 in ledger, name
        assert M2_S3B_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S3B_CANDIDATE_SHA256 in ledger, name
        assert M2_S3B_RECEIPT_SHA256 in ledger, name
        assert "packaged_runtime_smoke_verified=true" in ledger, name
        assert "same_host_portable_verified=false" in ledger, name
        assert "clean_machine_verified=false" in ledger, name
        assert "distribution_ready=false" in ledger, name
        assert "release_authorized=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name

    m2_s2d_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S2D"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G18"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G14"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "verification": _read("docs/ai/M2_S2D_VERIFICATION.md"),
        "risk": risk,
    }
    for name, ledger in m2_s2d_ledgers.items():
        assert M2_S2D_RECEIPT in ledger, name
        assert M2_S2D_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S2D_CANDIDATE_SHA256 in ledger, name
        assert M2_S2D_SCHEMA_SHA256 in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "package_contains_integration=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name

    m2_s2e_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S2E"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G19"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G15"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "verification": _read("docs/ai/M2_S2E_VERIFICATION.md"),
        "risk": risk,
    }
    for name, ledger in m2_s2e_ledgers.items():
        assert M2_S2E_RECEIPT in ledger, name
        assert M2_S2E_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S2E_CANDIDATE_SHA256 in ledger, name
        assert M2_S2E_SCHEMA_SHA256 in ledger, name
        assert "EXACTLY_REPRODUCED" in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "package_contains_integration=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name

    m2_s3a_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S3A"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G20"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G16"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "audit": _read("docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.md"),
        "risk": risk,
    }
    for name, ledger in m2_s3a_ledgers.items():
        assert M2_S3A_RECEIPT in ledger, name
        assert M2_S3A_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S3A_CANDIDATE_SHA256 in ledger, name
        assert M2_S3A_SCHEMA_SHA256 in ledger, name
        assert M2_S3A_AUDIT_SHA256 in ledger, name
        assert "package_rebuild_started=false" in ledger, name
        assert "distribution_ready=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name

    m2_s3b_ledgers = {
        "roadmap": _section(_read("docs/plans/ROADMAP.md"), "## M2-S3B"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G21"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G17"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3B outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3B deterministic candidate integration boundary",
        ),
        "verification": _read("docs/ai/M2_S3B_VERIFICATION.md"),
        "risk": risk,
    }
    for name, ledger in m2_s3b_ledgers.items():
        assert M2_S3B_RECEIPT in ledger, name
        assert M2_S3B_STATIC_BINDINGS_DIGEST in ledger, name
        assert M2_S3B_CANDIDATE_SHA256 in ledger, name
        assert M2_S3B_SCHEMA_SHA256 in ledger, name
        assert M2_S3B_RECEIPT_SHA256 in ledger, name
        assert "candidate_package_contains_integration=true" in ledger, name
        assert "historical_package_unchanged=true" in ledger, name
        assert "packaged_runtime_smoke_verified=false" in ledger, name
        assert "distribution_ready=false" in ledger, name
        assert "release_authorized=false" in ledger, name
        assert "device_gate_decision=UNVERIFIED" in ledger, name
        assert "d1_go=false" in ledger, name
        assert "authority_status=AUTHORITY_NOT_ISSUED" in ledger, name


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
    m2_s2a_heading = _section(roadmap, "## M2-S2A").splitlines()[0]
    assert "(HISTORICAL)" not in m2_s2a_heading
    m2_s2b_heading = _section(roadmap, "## M2-S2B").splitlines()[0]
    assert "(HISTORICAL)" not in m2_s2b_heading
    m2_s2d_heading = _section(roadmap, "## M2-S2D").splitlines()[0]
    assert "(HISTORICAL)" not in m2_s2d_heading
    m2_s3a = _section(roadmap, "## M2-S3A")
    assert "(HISTORICAL)" not in m2_s3a.splitlines()[0]
    for forbidden in (
        "CURRENT_SOURCE_PACKAGE_VERIFIED",
        "CLEAN_MACHINE_VERIFIED",
        "RELEASE_AUTHORIZED",
        "DISTRIBUTION_READY",
    ):
        assert forbidden not in m2_s3a
    current_task = _read("docs/ai/CURRENT_TASK.md")
    task_contract = _read("docs/ai/TASK_CONTRACT.md")
    for ledger in (current_task, task_contract):
        assert "Git metadata exists" in ledger
        assert "clean `main`" in ledger
        assert "7912bd9" in ledger


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

    assert "Status: unopened" in _section(
        roadmap, "## M2 - Capture and pose pipeline"
    )
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
        WORKSPACE_STATIC_BINDINGS_DIGEST
    )
    assert hashlib.sha256(candidate_bytes).hexdigest() == WORKSPACE_CANDIDATE_SHA256
    assert (
        hashlib.sha256(schema_path.read_bytes()).hexdigest()
        == M2_S3E_A_SCHEMA_SHA256
    )
    assert len(artifacts["source_inventory"]) == 70
    assert set(artifacts) - {"source_inventory"} == {
        "uv_lock",
        "pose_landmarker_lite_task",
        "blaze_face_short_range_tflite",
    }
    assert len(candidate["static_bindings"]["policy_preimages"]) == 60

    contract = _read("docs/ai/M2_D1_N2_AUTHORITY_CONTRACT.md")
    current_contract = contract.split(
        "### HISTORICAL_SUPERSEDED_NON_AUTHORIZING", maxsplit=1
    )[0]
    m2_ledgers = {
        "authority_contract": current_contract,
        "readiness_pack": _read("docs/spec/M2_D1_N2_READINESS_PACK.md"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "roadmap": _section(roadmap, "## M2 - Capture and pose pipeline"),
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

    m2_s2a_ledgers = {
        "roadmap": _section(roadmap, "## M2-S2A"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G15"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G11"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
    }
    m2_s2a_bindings = (
        "package_contains_integration=false",
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
    for name, ledger in m2_s2a_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s3c_ledgers = {
        "roadmap": _section(roadmap, "## M2-S3C"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G22"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G18"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3C outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3C packaged synthetic runtime smoke boundary",
        ),
        "verification": _read("docs/ai/M2_S3C_VERIFICATION.md"),
    }
    m2_s3c_bindings = (
        "historical_package_unchanged=true",
        "candidate_package_unchanged=true",
        "candidate_package_contains_integration=true",
        "packaged_runtime_smoke_verified=true",
        "same_host_portable_verified=false",
        "clean_machine_verified=false",
        "release_authorized=false",
        "distribution_ready=false",
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
        "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT=OPEN",
        "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT=OPEN",
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN",
    )
    for name, ledger in m2_s3c_ledgers.items():
        for binding in m2_s3c_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S3C_RECEIPT in ledger, name
        assert "same_host_portable_verified=true" not in ledger, name
        assert "clean_machine_verified=true" not in ledger, name
        assert "release_authorized=true" not in ledger, name
        assert "distribution_ready=true" not in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s3d_ledgers = {
        "roadmap": _section(roadmap, "## M2-S3D"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G23"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G19"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3D outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3D packaged evidence round-trip boundary",
        ),
        "verification": _read("docs/ai/M2_S3D_VERIFICATION.md"),
    }
    m2_s3d_bindings = (
        "round_trip_receipt_sha256=" + M2_S3D_RECEIPT_SHA256,
        "static_bindings_digest=" + M2_S3D_STATIC_BINDINGS_DIGEST,
        "candidate_exact_bytes_sha256=" + M2_S3D_CANDIDATE_SHA256,
        "binding_schema_exact_bytes_sha256=" + M2_S3D_SCHEMA_SHA256,
        "source_tool_inventory_count=64",
        "policy_preimage_count=55",
        "historical_package_unchanged=true",
        "candidate_package_unchanged=true",
        "candidate_package_contains_integration=true",
        "packaged_runtime_smoke_verified=true",
        "packaged_evidence_round_trip_verified=true",
        "same_host_portable_verified=false",
        "clean_machine_verified=false",
        "release_authorized=false",
        "distribution_ready=false",
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
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE=CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN",
    )
    for name, ledger in m2_s3d_ledgers.items():
        assert M2_S3D_RECEIPT in ledger, name
        for binding in m2_s3d_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "same_host_portable_verified=true" not in ledger, name
        assert "clean_machine_verified=true" not in ledger, name
        assert "release_authorized=true" not in ledger, name
        assert "distribution_ready=true" not in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    s3d_receipt_bytes = (
        ROOT / "docs/ai/M2_S3D_PACKAGED_EVIDENCE_ROUND_TRIP.json"
    ).read_bytes()
    assert hashlib.sha256(s3d_receipt_bytes).hexdigest() == M2_S3D_RECEIPT_SHA256
    s3d_receipt = json.loads(s3d_receipt_bytes)
    assert s3d_receipt["status"] == M2_S3D_RECEIPT
    assert s3d_receipt["body"]["reproducibility"]["byte_identical"] is True
    assert s3d_receipt["body"]["authority_ceiling"]["clean_machine_verified"] is False

    m2_s3e_a_ledgers = {
        "roadmap": _section(roadmap, "## M2-S3E-A"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G24"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G20"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3E-A outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3E-A same-host isolated portability boundary",
        ),
        "verification": _read("docs/ai/M2_S3E_A_VERIFICATION.md"),
        "risk": _read("docs/plans/RISK_REGISTER.md"),
    }
    m2_s3e_a_bindings = (
        "same_host_portability_receipt_sha256=" + M2_S3E_A_RECEIPT_SHA256,
        "static_bindings_digest=" + M2_S3E_A_STATIC_BINDINGS_DIGEST,
        "candidate_exact_bytes_sha256=" + M2_S3E_A_CANDIDATE_SHA256,
        "binding_schema_exact_bytes_sha256=" + M2_S3E_A_SCHEMA_SHA256,
        "source_tool_inventory_count=70",
        "policy_preimage_count=60",
        "historical_package_unchanged=true",
        "candidate_package_unchanged=true",
        "candidate_package_contains_integration=true",
        "packaged_runtime_smoke_verified=true",
        "packaged_evidence_round_trip_verified=true",
        "same_host_portable_verified=true",
        "clean_environment_handoff_ready=true",
        "clean_machine_verified=false",
        "release_authorized=false",
        "distribution_ready=false",
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
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN",
    )
    for name, ledger in m2_s3e_a_ledgers.items():
        assert M2_S3E_A_RECEIPT in ledger, name
        for binding in m2_s3e_a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert "clean_machine_verified=true" not in ledger, name
        assert "release_authorized=true" not in ledger, name
        assert "distribution_ready=true" not in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    s3e_a_receipt_bytes = (
        ROOT / "docs/ai/M2_S3E_A_SAME_HOST_PORTABILITY.json"
    ).read_bytes()
    assert hashlib.sha256(s3e_a_receipt_bytes).hexdigest() == M2_S3E_A_RECEIPT_SHA256
    s3e_a_receipt = json.loads(s3e_a_receipt_bytes)
    assert s3e_a_receipt["status"] == M2_S3E_A_RECEIPT
    assert s3e_a_receipt["body"]["reproducibility"]["byte_identical"] is True
    assert s3e_a_receipt["body"]["authority_ceiling"]["same_host_portable_verified"] is True
    assert s3e_a_receipt["body"]["authority_ceiling"]["clean_machine_verified"] is False

    m2_s2b_ledgers = {
        "roadmap": _section(roadmap, "## M2-S2B"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G16"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G12"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
    }
    for name, ledger in m2_s2b_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S2B_RECEIPT in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "run_kind=NOMINAL_20M" in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s2c_ledgers = {
        "roadmap": _section(roadmap, "## M2-S2C"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G17"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G13"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
    }
    for name, ledger in m2_s2c_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S2C_RECEIPT in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s2d_ledgers = {
        "roadmap": _section(roadmap, "## M2-S2D"),
        "acceptance": _section(
            _read("docs/plans/ACCEPTANCE_GATES.md"), "## G18"
        ),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G14"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "verification": _read("docs/ai/M2_S2D_VERIFICATION.md"),
    }
    for name, ledger in m2_s2d_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S2D_RECEIPT in ledger, name
        assert "evidence_kind=SIMULATED" in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s2e_ledgers = {
        "roadmap": _section(roadmap, "## M2-S2E"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G19"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G15"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "verification": _read("docs/ai/M2_S2E_VERIFICATION.md"),
    }
    for name, ledger in m2_s2e_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S2E_RECEIPT in ledger, name
        assert "EXACTLY_REPRODUCED" in ledger, name
        assert "SOURCE_REVISION_MISMATCH" in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s3a_ledgers = {
        "roadmap": _section(roadmap, "## M2-S3A"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G20"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G16"),
        "current_task": _read("docs/ai/CURRENT_TASK.md"),
        "task_contract": _read("docs/ai/TASK_CONTRACT.md"),
        "audit": _read("docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.md"),
    }
    for name, ledger in m2_s3a_ledgers.items():
        for binding in m2_s2a_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S3A_RECEIPT in ledger, name
        assert "package_contains_integration=true" not in ledger.splitlines(), name
        assert "package_rebuild_started=true" not in ledger, name
        assert "release_authorized=true" not in ledger, name
        assert "distribution_ready=true" not in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

    m2_s3b_ledgers = {
        "roadmap": _section(roadmap, "## M2-S3B"),
        "acceptance": _section(_read("docs/plans/ACCEPTANCE_GATES.md"), "## G21"),
        "quality": _section(_read("docs/ai/QUALITY_GATES.md"), "## G17"),
        "current_task": _section(
            _read("docs/ai/CURRENT_TASK.md"), "## Active M2-S3B outcome"
        ),
        "task_contract": _section(
            _read("docs/ai/TASK_CONTRACT.md"),
            "## M2-S3B deterministic candidate integration boundary",
        ),
        "verification": _read("docs/ai/M2_S3B_VERIFICATION.md"),
    }
    m2_s3b_bindings = (
        "historical_package_unchanged=true",
        "candidate_package_built=true",
        "candidate_package_contains_integration=true",
        "packaged_runtime_smoke_verified=false",
        "same_host_portable_verified=false",
        "clean_machine_verified=false",
        "release_authorized=false",
        "distribution_ready=false",
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
    for name, ledger in m2_s3b_ledgers.items():
        for binding in m2_s3b_bindings:
            assert binding in ledger, f"{name}: {binding}"
        assert M2_S3B_RECEIPT in ledger, name
        assert "packaged_runtime_smoke_verified=true" not in ledger, name
        assert "same_host_portable_verified=true" not in ledger, name
        assert "clean_machine_verified=true" not in ledger, name
        assert "release_authorized=true" not in ledger, name
        assert "distribution_ready=true" not in ledger, name
        assert "physical_camera_access_authorized=true" not in ledger, name
        assert "d1_go=true" not in ledger, name
        assert "research_ready=true" not in ledger, name
        assert "collection_authorized=true" not in ledger, name
        assert "authority_status=ISSUED" not in ledger, name

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
