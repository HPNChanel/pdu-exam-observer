"""Canonical M1-R1 withdrawal planning and closed receipt bodies."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Protocol, cast

from pdu_exam_observer.m1 import SchemaIntegrityError
from pdu_exam_observer.m1_r1 import ResearchStoreV3, _canonical_json, _root_identity_digest
from pdu_exam_observer.services.core import ReviewerAuthenticator


class ReconciliationBlocked(RuntimeError):
    """Current participant state cannot produce a safe reconciliation plan."""


class ChallengeRejected(PermissionError):
    """A step-up or single-use challenge failed a closed validation."""


class ProcedureAuthorityNotIssued(PermissionError):
    """No separately scoped procedure-governance authority is present."""


class ProcedureGovernanceAuthority(Protocol):
    def permits_procedure_import(
        self, *, authority_reference: str, source_document_sha256: str
    ) -> bool: ...


class ExternalAttestationAuthority(Protocol):
    """One non-serializable capability bound to one external challenge."""

    def permits_external_attestation(
        self,
        *,
        root_identity_digest: str,
        challenge_id: str,
        plan_sha256: str,
        target_id: str,
        procedure_authority_id: str,
    ) -> bool: ...


@dataclass(frozen=True)
class ReconciliationPlan:
    participant_id: str
    withdrawal_receipt_id: str
    participant_pseudonym: str
    target_state_version: int
    body: dict[str, object]
    canonical_json: str
    plan_sha256: str


@dataclass(frozen=True)
class ReconciliationReceipt:
    body: dict[str, object]
    canonical_json: str
    body_sha256: str

    @classmethod
    def from_plan(cls, plan: ReconciliationPlan) -> ReconciliationReceipt:
        targets = cast(list[dict[str, object]], plan.body["targets"])
        tasks = cast(list[dict[str, object]], plan.body["tasks"])
        local = [
            target
            for target in targets
            if target["target_kind"]
            in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
        ]
        external = [
            target for target in targets if target["target_kind"] == "EXTERNAL_COPY"
        ]
        local_verified = sum(
            target["state"] == "LOCAL_DELETION_VERIFIED" for target in local
        )
        external_attested = sum(
            target["state"] == "EXTERNAL_DELETION_ATTESTED" for target in external
        )
        blocked = sum(target["state"] == "BLOCKED" for target in targets)
        recovery = sum(target["state"] == "RECOVERY_REQUIRED" for target in targets)
        task_completed = 0
        for task in tasks:
            task_targets = [
                target
                for target in targets
                if target["withdrawal_task_id"] == task["withdrawal_task_id"]
            ]
            if task_targets and all(
                (
                    target["target_kind"] == "EXTERNAL_COPY"
                    and target["state"] == "EXTERNAL_DELETION_ATTESTED"
                )
                or (
                    target["target_kind"]
                    in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
                    and target["state"] == "LOCAL_DELETION_VERIFIED"
                )
                for target in task_targets
            ):
                task_completed += 1
        bases: list[str] = []
        if external_attested:
            bases.append("EXTERNAL_DELETION_ATTESTED")
        if local_verified:
            bases.append("LOCAL_DELETION_VERIFIED")
        body: dict[str, object] = {
            "blocked_target_total": blocked,
            "collection_authorized": False,
            "complete": bool(plan.body["complete"]),
            "completion_basis": bases,
            "external_deletion_attested_total": external_attested,
            "external_target_total": len(external),
            "human_review_required": True,
            "local_deletion_verified_total": local_verified,
            "local_target_total": len(local),
            "operational_ledger_version": 3,
            "participant_pseudonym": plan.participant_pseudonym,
            "plan_sha256": plan.plan_sha256,
            "real_data_deletion_authorized_for_this_run": False,
            "receipt_schema_version": 1,
            "recovery_required_total": recovery,
            "research_ready": False,
            "task_completed": task_completed,
            "task_total": len(tasks),
            "withdrawal_receipt_id": plan.withdrawal_receipt_id,
        }
        canonical = _canonical_json(body)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(body=body, canonical_json=canonical, body_sha256=digest)


class ReconciliationPlanner:
    """Build one redacted plan from one stable v3 read snapshot."""

    def __init__(self, store: ResearchStoreV3) -> None:
        if store.schema_version != 3:
            raise SchemaIntegrityError("reconciliation planner requires ledger v3")
        self.store = store

    def plan_for_session(self, session_id: str) -> ReconciliationPlan:
        self.store._opaque(session_id, "session id")
        with self.store.read_transaction() as connection:
            subject = connection.execute(
                "SELECT p.id participant_id,p.pseudonym,wr.id withdrawal_receipt_id "
                "FROM sessions s JOIN participants p ON p.id=s.participant_id "
                "LEFT JOIN withdrawal_receipts wr ON wr.participant_id=p.id "
                "WHERE s.id=? AND s.session_kind='RESEARCH'",
                (session_id,),
            ).fetchone()
            if subject is None:
                raise KeyError(session_id)
            if subject["withdrawal_receipt_id"] is None:
                raise ReconciliationBlocked("WITHDRAWAL_NOT_RECORDED")
            participant_id = str(subject["participant_id"])
            withdrawal_receipt_id = str(subject["withdrawal_receipt_id"])
            participant_pseudonym = str(subject["pseudonym"])
            tasks = connection.execute(
                "SELECT wt.id,wt.artifact_id,wt.status FROM withdrawal_tasks wt "
                "JOIN sessions s ON s.id=wt.withdrawal_subject_session_id "
                "WHERE s.participant_id=? ORDER BY wt.id",
                (participant_id,),
            ).fetchall()
            mappings = connection.execute(
                "SELECT wtt.withdrawal_task_id,wtt.target_id,wtt.target_kind,wtt.root_scope,"
                "wtt.state,wtt.state_version,wtt.blocker_code,wtt.artifact_id,"
                "rt.relative_path,rt.export_id,rt.expected_byte_size,rt.expected_sha256,"
                "rt.manifest_schema_version,rt.manifest_sha256,a.status artifact_status "
                "FROM withdrawal_task_targets wtt "
                "JOIN reconciliation_targets rt ON rt.id=wtt.target_id "
                "JOIN artifact_registry a ON a.id=wtt.artifact_id "
                "WHERE wtt.participant_id=? AND wtt.withdrawal_receipt_id=? "
                "ORDER BY wtt.target_id",
                (participant_id, withdrawal_receipt_id),
            ).fetchall()
            blockers = self._blockers(
                connection,
                participant_id=participant_id,
                tasks=tasks,
                mappings=mappings,
            )
            target_body = [
                {
                    "root_scope": str(row["root_scope"]),
                    "state": str(row["state"]),
                    "state_version": int(row["state_version"]),
                    "target_id": str(row["target_id"]),
                    "target_kind": str(row["target_kind"]),
                    "withdrawal_task_id": str(row["withdrawal_task_id"]),
                }
                for row in mappings
            ]
            task_body = [
                {
                    "artifact_id": str(row["artifact_id"]),
                    "withdrawal_task_id": str(row["id"]),
                }
                for row in tasks
            ]
            state_binding = [
                (
                    target["target_id"],
                    target["state"],
                    target["state_version"],
                )
                for target in target_body
            ]
            state_digest = hashlib.sha256(
                _canonical_json(state_binding).encode("utf-8")
            ).hexdigest()
            target_state_version = int(state_digest[:15], 16)
            local_total = sum(
                target["target_kind"]
                in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
                for target in target_body
            )
            external_total = sum(
                target["target_kind"] == "EXTERNAL_COPY" for target in target_body
            )
            terminal = all(
                (
                    target["target_kind"] == "EXTERNAL_COPY"
                    and target["state"] == "EXTERNAL_DELETION_ATTESTED"
                )
                or (
                    target["target_kind"]
                    in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
                    and target["state"] == "LOCAL_DELETION_VERIFIED"
                )
                for target in target_body
            )
            complete = bool(tasks) and not blockers and terminal
            body: dict[str, object] = {
                "blocker_codes": sorted(blockers),
                "complete": complete,
                "confirmation_phrase": f"DOI_SOAT {participant_pseudonym}",
                "external_target_total": external_total,
                "local_target_total": local_total,
                "operational_ledger_version": 3,
                "participant_id": participant_id,
                "participant_pseudonym": participant_pseudonym,
                "plan_schema_version": 1,
                "recovery_required_total": sum(
                    target["state"] == "RECOVERY_REQUIRED" for target in target_body
                ),
                "blocked_target_total": sum(
                    target["state"] == "BLOCKED" for target in target_body
                ),
                "target_state_version": target_state_version,
                "target_total": len(target_body),
                "targets": target_body,
                "task_total": len(task_body),
                "tasks": task_body,
                "withdrawal_receipt_id": withdrawal_receipt_id,
            }
            canonical = _canonical_json(body)
            plan_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            return ReconciliationPlan(
                participant_id=participant_id,
                withdrawal_receipt_id=withdrawal_receipt_id,
                participant_pseudonym=participant_pseudonym,
                target_state_version=target_state_version,
                body=body,
                canonical_json=canonical,
                plan_sha256=plan_sha256,
            )

    def _blockers(
        self,
        connection: sqlite3.Connection,
        *,
        participant_id: str,
        tasks: list[sqlite3.Row],
        mappings: list[sqlite3.Row],
    ) -> set[str]:
        blockers: set[str] = set()
        mapped_task_ids = {str(row["withdrawal_task_id"]) for row in mappings}
        if any(str(task["id"]) not in mapped_task_ids for task in tasks):
            blockers.add("TARGET_BINDING_MISSING")
        participant_sessions = "SELECT id FROM sessions WHERE participant_id=?"
        legacy_pending = connection.execute(
            "SELECT 1 FROM write_intents WHERE session_id IN ("
            + participant_sessions
            + ") AND status='PENDING' LIMIT 1",
            (participant_id,),
        ).fetchone()
        m2_pending = connection.execute(
            "SELECT 1 FROM m2_write_intents WHERE session_id IN ("
            + participant_sessions
            + ") AND status='PENDING' LIMIT 1",
            (participant_id,),
        ).fetchone()
        if legacy_pending is not None or m2_pending is not None:
            blockers.add("ACTIVE_WRITE_INTENT")
        m2_failed = connection.execute(
            "SELECT 1 FROM m2_write_intents WHERE session_id IN ("
            + participant_sessions
            + ") AND status='FAILED' LIMIT 1",
            (participant_id,),
        ).fetchone()
        if m2_failed is not None:
            blockers.add("FAILED_WRITE_INTENT_UNRESOLVED")
        m2_quarantined = connection.execute(
            "SELECT 1 FROM m2_write_intents WHERE session_id IN ("
            + participant_sessions
            + ") AND status='QUARANTINED' LIMIT 1",
            (participant_id,),
        ).fetchone()
        if m2_quarantined is not None:
            blockers.add("QUARANTINED_WRITE_INTENT_UNRESOLVED")
        if connection.execute(
            "SELECT 1 FROM reconciliation_holds WHERE participant_id=? AND status='ACTIVE'",
            (participant_id,),
        ).fetchone() is not None:
            blockers.add("APPROVED_HOLD_ACTIVE")
        for target in mappings:
            state = str(target["state"])
            if state == "BLOCKED":
                blockers.add(str(target["blocker_code"] or "TARGET_BLOCKED"))
            elif state == "RECOVERY_REQUIRED":
                blockers.add("RECOVERY_REQUIRED")
            if str(target["artifact_status"]) != "INVALIDATED":
                blockers.add("ARTIFACT_NOT_INVALIDATED")
            manifest = connection.execute(
                "SELECT * FROM artifact_manifests WHERE artifact_id=?",
                (target["artifact_id"],),
            ).fetchone()
            if manifest is None:
                blockers.add("MANIFEST_BINDING_INVALID")
                continue
            try:
                manifest_sha256 = self.store._manifest_binding_from_row(manifest)
                if manifest_sha256 != str(target["manifest_sha256"]):
                    blockers.add("MANIFEST_BINDING_INVALID")
                kind = str(target["target_kind"])
                if kind == "LOCAL_RESEARCH_FILE" and (
                    str(target["relative_path"])
                    != self.store._normalized_relative_path(str(manifest["relative_path"]))
                    or int(target["expected_byte_size"]) != int(manifest["byte_size"])
                    or str(target["expected_sha256"]) != str(manifest["sha256"])
                ):
                    blockers.add("MANIFEST_BINDING_INVALID")
            except (KeyError, TypeError, ValueError):
                blockers.add("MANIFEST_BINDING_INVALID")
        return blockers


@dataclass(frozen=True)
class IssuedChallenge:
    challenge_id: str
    challenge_token: str
    action: str
    target_id: str | None
    plan_sha256: str
    target_state_version: int
    confirmation_phrase: str
    expires_at: float


@dataclass(frozen=True)
class ConsumedChallenge:
    challenge_id: str
    execution_id: str
    execution_kind: str
    participant_id: str
    withdrawal_receipt_id: str
    plan_sha256: str
    target_id: str | None
    reviewer_session_digest: str


class ConfirmationService:
    """Recent PIN step-up plus one typed, single-use server-bound challenge."""

    _ACTIONS = {
        "EXECUTE_LOCAL_RECONCILIATION": "LOCAL_RUN",
        "ATTEST_EXTERNAL_DELETION": "EXTERNAL_ATTESTATION",
    }

    def __init__(
        self,
        *,
        store: ResearchStoreV3,
        planner: ReconciliationPlanner,
        authenticator: ReviewerAuthenticator,
        reviewer_session_digest: Callable[[str | None], str | None],
        register_reviewer_session_revocation: (
            Callable[[Callable[[str], None]], None] | None
        ) = None,
        clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.planner = planner
        self.authenticator = authenticator
        self._reviewer_session_digest = reviewer_session_digest
        self.clock = clock
        self.monotonic_clock = monotonic_clock
        self._challenge_deadlines: dict[str, tuple[float, float]] = {}
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE reconciliation_challenges SET status='EXPIRED' "
                "WHERE status='ISSUED'"
            )
        if register_reviewer_session_revocation is not None:
            register_reviewer_session_revocation(
                self.revoke_issued_challenges_for_reviewer_session
            )

    def revoke_issued_challenges_for_reviewer_session(
        self, reviewer_session_digest: str
    ) -> None:
        with self.store._root_lock:
            with self.store.transaction() as connection:
                challenge_ids = [
                    str(row["id"])
                    for row in connection.execute(
                        "SELECT id FROM reconciliation_challenges "
                        "WHERE reviewer_session_digest=? AND status='ISSUED'",
                        (reviewer_session_digest,),
                    ).fetchall()
                ]
                connection.execute(
                    "UPDATE reconciliation_challenges SET status='REVOKED' "
                    "WHERE reviewer_session_digest=? AND status='ISSUED'",
                    (reviewer_session_digest,),
                )
            for challenge_id in challenge_ids:
                self._challenge_deadlines.pop(challenge_id, None)

    def _session_digest(self, reviewer_token: str) -> str:
        digest = self._reviewer_session_digest(reviewer_token)
        if digest is None or len(digest) != 64:
            raise ChallengeRejected("REVIEWER_SESSION_INVALID")
        return digest

    def create_challenge(
        self,
        *,
        session_id: str,
        reviewer_token: str,
        pin: str,
        client_key: str,
        action: str,
        target_id: str | None,
    ) -> IssuedChallenge:
        reviewer_digest = self._session_digest(reviewer_token)
        now = self.clock()
        monotonic_now = self.monotonic_clock()
        expires_at = now + 120.0
        monotonic_expires_at = monotonic_now + 120.0
        if not math.isfinite(now) or not math.isfinite(expires_at):
            raise ChallengeRejected("CLOCK_INVALID")
        if not math.isfinite(monotonic_now) or not math.isfinite(monotonic_expires_at):
            raise ChallengeRejected("MONOTONIC_CLOCK_INVALID")
        login = self.authenticator.authenticate(
            pin,
            "reconciliation-step-up:" + client_key,
            monotonic_now,
        )
        if not login.accepted:
            suffix = "" if login.retry_after is None else f":{login.retry_after}"
            raise ChallengeRejected("PIN_STEP_UP_REJECTED" + suffix)
        if action not in self._ACTIONS:
            raise ChallengeRejected("CHALLENGE_ACTION_INVALID")
        with self.store._root_lock:
            plan = self.planner.plan_for_session(session_id)
            current_reviewer_digest = self._reviewer_session_digest(reviewer_token)
            current_now = self.clock()
            current_monotonic_now = self.monotonic_clock()
            if current_reviewer_digest != reviewer_digest:
                raise ChallengeRejected("REVIEWER_SESSION_INVALID")
            if not math.isfinite(current_now):
                raise ChallengeRejected("CLOCK_INVALID")
            if (
                not math.isfinite(current_monotonic_now)
                or current_monotonic_now < monotonic_now
            ):
                raise ChallengeRejected("MONOTONIC_CLOCK_INVALID")
            if current_now < now:
                raise ChallengeRejected("CLOCK_ROLLBACK_DETECTED")
            if current_now >= expires_at or current_monotonic_now >= monotonic_expires_at:
                raise ChallengeRejected("CHALLENGE_EXPIRED")
            blockers = [
                code
                for code in cast(list[str], plan.body["blocker_codes"])
                if code != "RECOVERY_REQUIRED"
            ]
            if blockers:
                raise ChallengeRejected("PLAN_BLOCKED:" + blockers[0])
            targets = cast(list[dict[str, object]], plan.body["targets"])
            if action == "EXECUTE_LOCAL_RECONCILIATION":
                if target_id is not None:
                    raise ChallengeRejected("LOCAL_CHALLENGE_MUST_NOT_BIND_TARGET")
                if not any(
                    target["target_kind"]
                    in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
                    and target["state"] in {"PENDING_CONFIRMATION", "RECOVERY_REQUIRED"}
                    for target in targets
                ):
                    raise ChallengeRejected("NO_LOCAL_TARGET_REQUIRES_RECONCILIATION")
                bound_kind = None
                root_scope = None
            else:
                match = next(
                    (
                        target
                        for target in targets
                        if target["target_id"] == target_id
                        and target["target_kind"] == "EXTERNAL_COPY"
                        and target["root_scope"] == "EXTERNAL_ATTESTATION"
                        and target["state"] in {"PENDING_CONFIRMATION", "RECOVERY_REQUIRED"}
                    ),
                    None,
                )
                if match is None or target_id is None:
                    raise ChallengeRejected("EXTERNAL_TARGET_BINDING_INVALID")
                bound_kind = "EXTERNAL_COPY"
                root_scope = "EXTERNAL_ATTESTATION"
            challenge_id = "challenge-" + token_urlsafe(18)
            challenge_token = token_urlsafe(32)
            token_digest = hashlib.sha256(challenge_token.encode("utf-8")).hexdigest()
            step_up_id = "step-up-" + token_urlsafe(18)
            with self.store.transaction() as connection:
                epoch = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(authentication_epoch),-1)+1 "
                        "FROM reviewer_step_up_authentications"
                    ).fetchone()[0]
                )
                connection.execute(
                    "INSERT INTO reviewer_step_up_authentications("
                    "id,reviewer_session_digest,authentication_epoch,verified_at,expires_at,"
                    "consumed_at) VALUES(?,?,?,?,?,NULL)",
                    (step_up_id, reviewer_digest, epoch, now, expires_at),
                )
                connection.execute(
                    "INSERT INTO reconciliation_challenges("
                    "id,participant_id,withdrawal_receipt_id,reviewer_session_digest,"
                    "token_digest,plan_sha256,target_state_version,step_up_authentication_id,"
                    "step_up_verified_at,step_up_expires_at,target_id,target_kind,root_scope,"
                    "action,status,issued_at,expires_at,consumed_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ISSUED',?,?,NULL)",
                    (
                        challenge_id,
                        plan.participant_id,
                        plan.withdrawal_receipt_id,
                        reviewer_digest,
                        token_digest,
                        plan.plan_sha256,
                        plan.target_state_version,
                        step_up_id,
                        now,
                        expires_at,
                        target_id,
                        bound_kind,
                        root_scope,
                        action,
                        now,
                        expires_at,
                    ),
                )
            self._challenge_deadlines[challenge_id] = (
                monotonic_now,
                monotonic_expires_at,
            )
            return IssuedChallenge(
                challenge_id=challenge_id,
                challenge_token=challenge_token,
                action=action,
                target_id=target_id,
                plan_sha256=plan.plan_sha256,
                target_state_version=plan.target_state_version,
                confirmation_phrase=str(plan.body["confirmation_phrase"]),
                expires_at=expires_at,
            )

    def consume_challenge(
        self,
        *,
        session_id: str,
        reviewer_token: str,
        challenge_token: str,
        confirmation_phrase: str,
    ) -> ConsumedChallenge:
        consumed, _attestation = self._consume(
            session_id=session_id,
            reviewer_token=reviewer_token,
            challenge_token=challenge_token,
            confirmation_phrase=confirmation_phrase,
            procedure_authority_id=None,
            external_authority=None,
        )
        return consumed

    def _consume(
        self,
        *,
        session_id: str,
        reviewer_token: str,
        challenge_token: str,
        confirmation_phrase: str,
        procedure_authority_id: str | None,
        external_authority: ExternalAttestationAuthority | None,
    ) -> tuple[ConsumedChallenge, dict[str, object] | None]:
        reviewer_digest = self._session_digest(reviewer_token)
        token_digest = hashlib.sha256(challenge_token.encode("utf-8")).hexdigest()
        rejection: str | None = None
        consumed: ConsumedChallenge | None = None
        attestation: dict[str, object] | None = None
        with self.store._root_lock:
            plan = self.planner.plan_for_session(session_id)
            current_reviewer_digest = self._reviewer_session_digest(reviewer_token)
            with self.store.transaction() as connection:
                now = self.clock()
                monotonic_now = self.monotonic_clock()
                challenge = connection.execute(
                    "SELECT * FROM reconciliation_challenges WHERE token_digest=?",
                    (token_digest,),
                ).fetchone()
                if challenge is None:
                    rejection = "CHALLENGE_INVALID"
                elif str(challenge["status"]) == "CONSUMED":
                    rejection = "CHALLENGE_ALREADY_CONSUMED"
                elif str(challenge["status"]) != "ISSUED":
                    rejection = "CHALLENGE_NOT_ACTIVE"
                elif current_reviewer_digest != reviewer_digest:
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='REVOKED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "REVIEWER_SESSION_INVALID"
                elif not math.isfinite(now):
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='REVOKED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "CLOCK_INVALID"
                elif str(challenge["reviewer_session_digest"]) != reviewer_digest:
                    rejection = "REVIEWER_SESSION_INVALID"
                elif (deadline := self._challenge_deadlines.get(str(challenge["id"]))) is None:
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='EXPIRED' WHERE id=?",
                        (challenge["id"],),
                    )
                    rejection = "CHALLENGE_EXPIRED"
                elif (
                    not math.isfinite(monotonic_now)
                    or monotonic_now < deadline[0]
                ):
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='REVOKED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "MONOTONIC_CLOCK_INVALID"
                elif monotonic_now >= deadline[1]:
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='EXPIRED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "CHALLENGE_EXPIRED"
                elif now < float(challenge["issued_at"]):
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='REVOKED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "CLOCK_ROLLBACK_DETECTED"
                elif now >= float(challenge["expires_at"]):
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='EXPIRED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "CHALLENGE_EXPIRED"
                elif confirmation_phrase != str(plan.body["confirmation_phrase"]):
                    rejection = "CONFIRMATION_PHRASE_MISMATCH"
                elif (
                    str(challenge["participant_id"]) != plan.participant_id
                    or str(challenge["withdrawal_receipt_id"])
                    != plan.withdrawal_receipt_id
                    or str(challenge["plan_sha256"]) != plan.plan_sha256
                    or int(challenge["target_state_version"])
                    != plan.target_state_version
                ):
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='REVOKED' WHERE id=?",
                        (challenge["id"],),
                    )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
                    rejection = "PLAN_CHANGED"
                elif challenge["action"] == "ATTEST_EXTERNAL_DELETION" and (
                    procedure_authority_id is None
                ):
                    rejection = "EXTERNAL_ATTESTATION_REQUIRES_PROCEDURE"
                elif challenge["action"] == "ATTEST_EXTERNAL_DELETION" and (
                    external_authority is None
                    or challenge["target_id"] is None
                    or not external_authority.permits_external_attestation(
                        root_identity_digest=_root_identity_digest(self.store.root),
                        challenge_id=str(challenge["id"]),
                        plan_sha256=str(challenge["plan_sha256"]),
                        target_id=str(challenge["target_id"]),
                        procedure_authority_id=cast(str, procedure_authority_id),
                    )
                ):
                    raise ProcedureAuthorityNotIssued("AUTHORITY_NOT_ISSUED")
                else:
                    action = str(challenge["action"])
                    execution_kind = self._ACTIONS[action]
                    execution_id = "execution-" + token_urlsafe(18)
                    connection.execute(
                        "INSERT INTO reconciliation_executions("
                        "id,challenge_id,execution_kind,created_at) VALUES(?,?,?,?)",
                        (execution_id, challenge["id"], execution_kind, now),
                    )
                    connection.execute(
                        "UPDATE reconciliation_challenges SET status='CONSUMED',consumed_at=? "
                        "WHERE id=? AND status='ISSUED'",
                        (now, challenge["id"]),
                    )
                    connection.execute(
                        "UPDATE reviewer_step_up_authentications SET consumed_at=? WHERE id=?",
                        (now, challenge["step_up_authentication_id"]),
                    )
                    consumed = ConsumedChallenge(
                        challenge_id=str(challenge["id"]),
                        execution_id=execution_id,
                        execution_kind=execution_kind,
                        participant_id=str(challenge["participant_id"]),
                        withdrawal_receipt_id=str(challenge["withdrawal_receipt_id"]),
                        plan_sha256=str(challenge["plan_sha256"]),
                        target_id=None
                        if challenge["target_id"] is None
                        else str(challenge["target_id"]),
                        reviewer_session_digest=reviewer_digest,
                    )
                    if procedure_authority_id is not None:
                        attestation = self._insert_external_attestation(
                            connection,
                            consumed=consumed,
                            procedure_authority_id=procedure_authority_id,
                            attested_at=now,
                        )
                    self._challenge_deadlines.pop(str(challenge["id"]), None)
        if rejection is not None:
            raise ChallengeRejected(rejection)
        if consumed is None:
            raise ChallengeRejected("CHALLENGE_INVALID")
        return consumed, attestation

    def import_procedure_authority(
        self,
        *,
        authority_id: str,
        authority_reference: str,
        source_document_sha256: str,
        authority: ProcedureGovernanceAuthority | None,
    ) -> None:
        if authority is None or not authority.permits_procedure_import(
            authority_reference=authority_reference,
            source_document_sha256=source_document_sha256,
        ):
            raise ProcedureAuthorityNotIssued("AUTHORITY_NOT_ISSUED")
        self.store._opaque(authority_id, "procedure authority id")
        if not 1 <= len(authority_reference) <= 128 or not all(
            character.isascii() and (character.isalnum() or character in "._-")
            for character in authority_reference
        ):
            raise ProcedureAuthorityNotIssued("PROCEDURE_REFERENCE_INVALID")
        if len(source_document_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in source_document_sha256
        ):
            raise ProcedureAuthorityNotIssued("PROCEDURE_SOURCE_DIGEST_INVALID")
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO approved_procedure_authorities("
                "id,authority_reference,procedure_kind,source_document_sha256,status,"
                "approved_at,expires_at,revoked_at) "
                "VALUES(?,?,'EXTERNAL_DELETION',?,'APPROVED',?,NULL,NULL)",
                (
                    authority_id,
                    authority_reference,
                    source_document_sha256,
                    self.clock(),
                ),
            )

    def attest_external_deletion(
        self,
        *,
        session_id: str,
        reviewer_token: str,
        challenge_token: str,
        confirmation_phrase: str,
        procedure_authority_id: str,
        authority: ExternalAttestationAuthority | None,
    ) -> dict[str, object]:
        _consumed, attestation = self._consume(
            session_id=session_id,
            reviewer_token=reviewer_token,
            challenge_token=challenge_token,
            confirmation_phrase=confirmation_phrase,
            procedure_authority_id=procedure_authority_id,
            external_authority=authority,
        )
        if attestation is None:
            raise ChallengeRejected("EXTERNAL_ATTESTATION_NOT_RECORDED")
        return attestation

    def _insert_external_attestation(
        self,
        connection: sqlite3.Connection,
        *,
        consumed: ConsumedChallenge,
        procedure_authority_id: str,
        attested_at: float,
    ) -> dict[str, object]:
        if consumed.execution_kind != "EXTERNAL_ATTESTATION" or consumed.target_id is None:
            raise ChallengeRejected("EXTERNAL_TARGET_BINDING_INVALID")
        procedure = connection.execute(
            "SELECT status,approved_at,expires_at,revoked_at "
            "FROM approved_procedure_authorities WHERE id=? AND procedure_kind='EXTERNAL_DELETION'",
            (procedure_authority_id,),
        ).fetchone()
        if (
            procedure is None
            or procedure["status"] != "APPROVED"
            or procedure["revoked_at"] is not None
            or float(procedure["approved_at"]) > attested_at
            or (
                procedure["expires_at"] is not None
                and float(procedure["expires_at"]) <= attested_at
            )
        ):
            raise ChallengeRejected("PROCEDURE_AUTHORITY_NOT_CURRENT")
        mapping = connection.execute(
            "SELECT withdrawal_task_id,target_kind,root_scope,state "
            "FROM withdrawal_task_targets WHERE participant_id=? "
            "AND withdrawal_receipt_id=? AND target_id=?",
            (
                consumed.participant_id,
                consumed.withdrawal_receipt_id,
                consumed.target_id,
            ),
        ).fetchone()
        if (
            mapping is None
            or mapping["target_kind"] != "EXTERNAL_COPY"
            or mapping["root_scope"] != "EXTERNAL_ATTESTATION"
            or mapping["state"] not in {"PENDING_CONFIRMATION", "RECOVERY_REQUIRED"}
        ):
            raise ChallengeRejected("EXTERNAL_TARGET_BINDING_INVALID")
        attestation_id = "attestation-" + token_urlsafe(18)
        connection.execute(
            "INSERT INTO external_deletion_attestations("
            "id,execution_id,execution_kind,participant_id,withdrawal_receipt_id,"
            "plan_sha256,withdrawal_task_id,target_id,target_kind,root_scope,"
            "challenge_action,challenge_id,procedure_authority_id,reviewer_session_digest,"
            "attested_at) VALUES(?,?,'EXTERNAL_ATTESTATION',?,?,?,?,?,"
            "'EXTERNAL_COPY','EXTERNAL_ATTESTATION','ATTEST_EXTERNAL_DELETION',?,?,?,?)",
            (
                attestation_id,
                consumed.execution_id,
                consumed.participant_id,
                consumed.withdrawal_receipt_id,
                consumed.plan_sha256,
                mapping["withdrawal_task_id"],
                consumed.target_id,
                consumed.challenge_id,
                procedure_authority_id,
                consumed.reviewer_session_digest,
                attested_at,
            ),
        )
        connection.execute(
            "UPDATE withdrawal_task_targets SET state='EXTERNAL_DELETION_ATTESTED',"
            "state_version=state_version+1,blocker_code=NULL,updated_at=? "
            "WHERE withdrawal_task_id=? AND target_id=?",
            (attested_at, mapping["withdrawal_task_id"], consumed.target_id),
        )
        return {
            "attestation_id": attestation_id,
            "state": "EXTERNAL_DELETION_ATTESTED",
            "target_id": consumed.target_id,
        }
