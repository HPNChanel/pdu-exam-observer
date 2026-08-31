# ruff: noqa: E501

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class SessionState(StrEnum):
    DRAFT = "DRAFT"
    CONSENT_CONFIRMED = "CONSENT_CONFIRMED"
    PREFLIGHT_READY = "PREFLIGHT_READY"
    RECORDING = "RECORDING"
    SEALED = "SEALED"
    FAILED = "FAILED"
    WITHDRAWN = "WITHDRAWN"


class SessionKind(StrEnum):
    DEMO = "DEMO"
    RESEARCH = "RESEARCH"


class StudyStatus(StrEnum):
    APPROVAL_PENDING = "APPROVAL_PENDING"


class ReadinessGateCode(StrEnum):
    INSTITUTIONAL_APPROVAL_REQUIRED = "INSTITUTIONAL_APPROVAL_REQUIRED"
    OPERATOR_CONSENT_REQUIRED = "OPERATOR_CONSENT_REQUIRED"
    RETENTION_DECISION_REQUIRED = "RETENTION_DECISION_REQUIRED"
    RETENTION_AUTHORITY_UNVERIFIED = "RETENTION_AUTHORITY_UNVERIFIED"
    STORAGE_ENCRYPTION_UNVERIFIED = "STORAGE_ENCRYPTION_UNVERIFIED"
    STORAGE_ACL_UNVERIFIED = "STORAGE_ACL_UNVERIFIED"
    RESEARCH_COLLECTION_NOT_IMPLEMENTED = "RESEARCH_COLLECTION_NOT_IMPLEMENTED"


class ArtifactStatus(StrEnum):
    VALID = "VALID"
    INVALIDATED = "INVALIDATED"


class WithdrawalTaskStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class ParticipantWithdrawalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    withdrawal_receipt_id: str | None
    participant_pseudonym: str
    terminal: bool
    task_count: int = Field(ge=0)


class _ResearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResearchStudyCreateRequest(_ResearchRequest):
    study_code: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ResearchParticipantCreateRequest(_ResearchRequest):
    study_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class ResearchSessionCreateRequest(_ResearchRequest):
    study_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    participant_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    retention_policy_reference: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$"
    )
    retention_end_date: date | None = None

    @model_validator(mode="after")
    def no_competing_retention_values(self) -> "ResearchSessionCreateRequest":
        if self.retention_policy_reference is not None and self.retention_end_date is not None:
            raise ValueError("provide one retention value, not both")
        if self.retention_end_date is not None and self.retention_end_date < date.today():
            raise ValueError("retention end date may not be in the past")
        return self


class ConsentConfirmationRequest(_ResearchRequest):
    consent_receipt_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    consent_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


class ReconciliationChallengeRequest(_ResearchRequest):
    pin: str = Field(min_length=1, max_length=128)
    action: Literal[
        "EXECUTE_LOCAL_RECONCILIATION", "ATTEST_EXTERNAL_DELETION"
    ]
    target_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )


class ReconciliationExecutionRequest(_ResearchRequest):
    challenge_token: str = Field(min_length=32, max_length=128)
    confirmation_phrase: str = Field(min_length=1, max_length=256)


class ExternalDeletionAttestationRequest(ReconciliationExecutionRequest):
    procedure_authority_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )


class ResearchLabel(StrEnum):
    NORMAL = "NORMAL"
    BENIGN_CONFOUNDER = "BENIGN_CONFOUNDER"
    PROLONGED_HEAD_DOWN = "PROLONGED_HEAD_DOWN"
    PROLONGED_SIDE_LOOK = "PROLONGED_SIDE_LOOK"
    NO_PERSON = "NO_PERSON"
    MULTIPLE_PEOPLE = "MULTIPLE_PEOPLE"
    UNCERTAIN = "UNCERTAIN"


class OperatorOutcome(StrEnum):
    NORMAL = "NORMAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    TECHNICAL_INSUFFICIENT = "TECHNICAL_INSUFFICIENT"


class SourceKind(StrEnum):
    REAL = "REAL"
    AI_RENDERED = "AI_RENDERED"
    AUGMENTED = "AUGMENTED"


class ConfidenceStatus(StrEnum):
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"
    CALIBRATED = "CALIBRATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AlertEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    label: ResearchLabel
    source_kind: SourceKind
    confidence: None = None
    confidence_status: ConfidenceStatus = ConfidenceStatus.MODEL_UNAVAILABLE
    duration_seconds: int = Field(ge=0)
    contributing_signals: tuple[str, ...]
    demo_index: int = Field(ge=1)


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    session_id: str
    state: SessionState
    event_seq: int
    submitted: bool
    duration_seconds: int
    remaining_seconds: int | None
    started_at_utc: str | None


class SessionCreateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    session_id: str
    pairing_code: str


class PairingRequest(BaseModel):
    pairing_code: str = Field(min_length=1, max_length=128)


class ReviewerLoginRequest(BaseModel):
    pin: str = Field(min_length=1, max_length=128)


class ReviewerLoginResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    token_type: Literal["Bearer"] = "Bearer"
    access_token: str = Field(min_length=1)
    expires_at_utc: str
    reviewer: str


class ReviewerSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA_VERSION
    expires_at_utc: str
    reviewer: str


class EventStreamRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    after_event_seq: int = Field(ge=0)


class AnswerRequest(BaseModel):
    answer_id: str = Field(min_length=1, max_length=128)
    question_id: str = Field(min_length=1, max_length=128)
    value: str | int | float | bool | None


class DemoReplayRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
