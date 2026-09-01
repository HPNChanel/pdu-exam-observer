export type ApiSurface = 'exam' | 'monitor';
export type SessionState = 'DRAFT' | 'CONSENT_CONFIRMED' | 'PREFLIGHT_READY' | 'RECORDING' | 'SEALED' | 'FAILED' | 'WITHDRAWN';
export type Health = { schemaVersion: number; status: 'ok' };
export type SessionSnapshot = { sessionId: string; eventSeq: number; submitted: boolean; state: SessionState; durationSeconds: number; remainingSeconds: number | null; startedAtUtc: string | null };
export type ReviewerEvent = { id: string; eventSeq: number; kind: 'signal' | 'technical'; occurredAt: string; title: string; confidence: number | null; confidenceStatus: 'MODEL_UNAVAILABLE' | 'INSUFFICIENT' | 'CALIBRATED' | 'NOT_APPLICABLE'; durationSeconds: number; signals: string[] };
export type StreamMessage = { kind: 'snapshot'; snapshot: SessionSnapshot } | { kind: 'event'; event: ReviewerEvent };
export type AnswerIntent = { answerId: string; questionId: string; value: string };
export type ResearchStudy = { id: string; studyCode: string };
export type ResearchParticipant = { id: string; pseudonym: string };
export type ResearchSession = { id: string; studyId?: string; participantId?: string; participantPseudonym?: string; state: SessionState };
export type ResearchReadiness = { ready: boolean; blockingGates: string[] };
export type ResearchRecovery = { sessionId: string; state: SessionState; collectionBlocked: boolean; reauthenticationRequired: boolean };
export type WithdrawalStatus = { participantPseudonym: string; withdrawalReceiptId: string | null; terminal: boolean; taskCount: number };
export type ResearchSessionIntent = { studyId: string; participantId: string; retentionPolicyReference?: string; retentionEndDate?: string };
export type ConsentConfirmationIntent = { consentReceiptId: string; consentVersion: string };
export type ReconciliationTarget = { targetId: string; targetKind: 'LOCAL_RESEARCH_FILE' | 'LOCAL_EXPORT_STAGING_FILE' | 'EXTERNAL_COPY'; state: string };
export type ReconciliationPlan = { participantPseudonym: string; planSha256: string; confirmationPhrase: string; localTargetTotal: number; externalTargetTotal: number; blockedTargetTotal: number; recoveryRequiredTotal: number; complete: boolean; blockerCodes: string[]; targets: ReconciliationTarget[] };
export type ReconciliationChallenge = { challengeId: string; challengeToken: string; planSha256: string; confirmationPhrase: string; expiresAt: number };
export type SyntheticReviewRunKind = 'PREFLIGHT_60S' | 'NOMINAL_20M';
export type SyntheticReviewReceipt = { schemaVersion: 1; status: string; integrationStatus: 'PERSISTED' | 'NOT_PERSISTED'; evidenceKind: 'SIMULATED'; runKind: SyntheticReviewRunKind; d1Outcome: 'BACKEND_CONTRACT_PASS' | 'NO_GO' | null; d1FailureCode: string | null; integrationFailureCode: string | null; deviceGateDecision: 'UNVERIFIED'; d1Go: false; authorityStatus: 'AUTHORITY_NOT_ISSUED'; physicalCameraAccessAuthorized: false; participantCollectionAuthorized: false; collectionAuthorized: false; observationCount: number; observationDigest: string | null; d1ReceiptDigest: string | null; artifactId: string | null; artifactSha256: string | null; manifestSchemaVersion: 2 | null; packageContainsIntegration: false; resultDigest: string };
export type SyntheticReviewRun = { schemaVersion: 1; requestId: string; runSequence: number; runKind: SyntheticReviewRunKind; jobStatus: 'QUEUED' | 'RUNNING' | 'TERMINAL'; serviceFailureCode: string | null; receipt: SyntheticReviewReceipt | null };
export type SyntheticEvidenceDownload = { bytes: Uint8Array; filename: string; sha256: string };

const eventTitles = {
  BENIGN_CONFOUNDER: 'T\u01b0 th\u1ebf c\u00f3 th\u1ec3 do y\u1ebfu t\u1ed1 l\u00e0nh t\u00ednh',
  PROLONGED_HEAD_DOWN: '\u0110\u1ea7u h\u01b0\u1edbng xu\u1ed1ng k\u00e9o d\u00e0i',
  PROLONGED_SIDE_LOOK: 'H\u01b0\u1edbng nh\u00ecn sang b\u00ean k\u00e9o d\u00e0i',
  NO_PERSON: 'Kh\u00f4ng c\u00f3 ng\u01b0\u1eddi trong khung quan s\u00e1t',
  MULTIPLE_PEOPLE: 'C\u00f3 nhi\u1ec1u ng\u01b0\u1eddi trong khung quan s\u00e1t',
  UNCERTAIN: 'D\u1eef li\u1ec7u quan s\u00e1t ch\u01b0a ch\u1eafc ch\u1eafn',
  NORMAL: 'T\u00edn hi\u1ec7u trong ng\u01b0\u1ee1ng th\u00f4ng th\u01b0\u1eddng',
} as const;
const demoEventTitles = {
  session_started: 'Phi\u00ean m\u00f4 ph\u1ecfng b\u1eaft \u0111\u1ea7u',
  answer_recorded: 'C\u00e2u tr\u1ea3 l\u1eddi m\u00f4 ph\u1ecfng \u0111\u00e3 \u0111\u01b0\u1ee3c ghi nh\u1eadn',
  technical_state: 'D\u1eef li\u1ec7u k\u1ef9 thu\u1eadt ch\u01b0a \u0111\u1ee7',
  session_stopped: 'Phi\u00ean m\u00f4 ph\u1ecfng \u0111\u00e3 k\u1ebft th\u00fac',
} as const;

type BackendEvent = {
  event_seq: number;
  type: string;
  label?: keyof typeof eventTitles;
  confidence?: number | null;
  confidence_status?: ReviewerEvent['confidenceStatus'];
  duration_seconds?: number;
  contributing_signals?: string[];
  fixture_event_type?: string;
  source_kind?: string;
  session_id?: string;
  state?: SessionState;
  submitted?: boolean;
  remaining_seconds?: number | null;
  started_at_utc?: string | null;
};
type BackendSnapshot = {
  session_id: string;
  event_seq: number;
  submitted: boolean;
  state: SessionState;
  duration_seconds: number;
  remaining_seconds: number | null;
  started_at_utc: string | null;
};
type StoredReviewerSession = {
  schemaVersion: 1;
  accessToken: string;
  expiresAtUtc: string;
  reviewer: string;
};
type BackendReviewerLogin = {
  schema_version: number;
  token_type: string;
  access_token: string;
  expires_at_utc: string;
  reviewer: string;
};
type BackendReviewerSession = { schema_version: number; expires_at_utc: string; reviewer: string };

const reviewerStorageKey = 'pdu-exam-observer.reviewer-session.v1';
const maxReconnectAttempts = 3;
const reconnectDelayMs = 100;
type DemoEventType = keyof typeof demoEventTitles;

export class ApiError extends Error {
  constructor(readonly status: number, readonly retryAfter?: number, readonly code?: string, readonly detail?: string) {
    super(`API request failed (${status})`);
  }
}

export const isMissingResearchRoute = (error: unknown): error is ApiError => error instanceof ApiError && error.status === 404 && error.detail === 'Not Found';

export const newIdempotencyKey = () => globalThis.crypto?.randomUUID?.() ?? `pdu-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const readCookie = (name: string): string | undefined => document.cookie.split('; ').find((entry) => entry.startsWith(`${name}=`))?.slice(name.length + 1);
const mapSnapshot = (snapshot: BackendSnapshot): SessionSnapshot => ({ sessionId: snapshot.session_id, eventSeq: snapshot.event_seq, submitted: snapshot.submitted, state: snapshot.state, durationSeconds: snapshot.duration_seconds, remainingSeconds: snapshot.remaining_seconds, startedAtUtc: snapshot.started_at_utc });
const isDemoEventType = (value: string | undefined): value is DemoEventType => value !== undefined && Object.prototype.hasOwnProperty.call(demoEventTitles, value);
const mapEvent = (event: BackendEvent): ReviewerEvent | undefined => {
  if (event.type === 'AlertEvent' && event.label && event.confidence_status) {
    return { id: `event-${event.event_seq}`, eventSeq: event.event_seq, kind: event.confidence_status === 'CALIBRATED' ? 'signal' : 'technical', occurredAt: `#${event.event_seq}`, title: eventTitles[event.label], confidence: event.confidence ?? null, confidenceStatus: event.confidence_status, durationSeconds: event.duration_seconds ?? 0, signals: event.contributing_signals ?? [] };
  }
  if (event.type !== 'DemoEvent' || event.confidence !== null || event.source_kind !== 'synthetic_demo' || !event.confidence_status || !isDemoEventType(event.fixture_event_type)) return undefined;
  return { id: `event-${event.event_seq}`, eventSeq: event.event_seq, kind: 'technical', occurredAt: `#${event.event_seq}`, title: demoEventTitles[event.fixture_event_type], confidence: null, confidenceStatus: event.confidence_status, durationSeconds: 0, signals: ['synthetic_demo'] };
};
const isSnapshot = (event: BackendEvent): event is BackendEvent & BackendSnapshot => event.type === 'SessionSnapshot' && Boolean(event.session_id && event.state && event.submitted !== undefined && event.duration_seconds !== undefined);
const sessionStates: readonly SessionState[] = ['DRAFT', 'CONSENT_CONFIRMED', 'PREFLIGHT_READY', 'RECORDING', 'SEALED', 'FAILED', 'WITHDRAWN'];
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;
const isSessionState = (value: unknown): value is SessionState => typeof value === 'string' && sessionStates.includes(value as SessionState);
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === 'string');
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => { const actual = Object.keys(value).sort(); const wanted = [...expected].sort(); return actual.length === wanted.length && actual.every((key, index) => key === wanted[index]); };
const syntheticAuthorityKeys = ['authority_status', 'capability_status', 'collection_authorized', 'd1_go', 'device_gate_decision', 'evidence_kind', 'execution_authorized', 'package_contains_integration', 'participant_collection_authorized', 'physical_camera_access_authorized', 'production_reconciler_implemented', 'production_reconciler_real_storage_verified', 'real_data_deletion_authorized', 'research_ready', 'schema_version'] as const;
const syntheticRecordKeys = ['schema_version', 'request_id', 'run_sequence', 'run_kind', 'job_status', 'service_failure_code', 'receipt'] as const;
const syntheticReceiptKeys = ['artifact_id', 'artifact_sha256', 'authority_status', 'collection_authorized', 'd1_failure_code', 'd1_go', 'd1_outcome', 'd1_receipt_digest', 'device_gate_decision', 'evidence_kind', 'integration_failure_code', 'integration_status', 'manifest_schema_version', 'observation_count', 'observation_digest', 'package_contains_integration', 'participant_collection_authorized', 'physical_camera_access_authorized', 'result_digest', 'run_kind', 'schema_version', 'status'] as const;
const hasClosedSyntheticAuthority = (value: Record<string, unknown>) => value.schema_version === 1 && value.capability_status === 'SYNTHETIC_REVIEW_ONLY' && value.authority_status === 'AUTHORITY_NOT_ISSUED' && value.collection_authorized === false && value.d1_go === false && value.device_gate_decision === 'UNVERIFIED' && value.evidence_kind === 'SIMULATED' && value.execution_authorized === false && value.package_contains_integration === false && value.participant_collection_authorized === false && value.physical_camera_access_authorized === false && value.production_reconciler_implemented === false && value.production_reconciler_real_storage_verified === false && value.real_data_deletion_authorized === false && value.research_ready === false;
const invalidSyntheticResponse = (): never => { throw new Error('Synthetic review API response is invalid'); };
const isDigest = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const isNullableDigest = (value: unknown): value is string | null => value === null || isDigest(value);
const mapSyntheticReceipt = (value: unknown, expectedRunKind: SyntheticReviewRunKind): SyntheticReviewReceipt => {
  if (!isRecord(value) || !exactKeys(value, syntheticReceiptKeys) || value.schema_version !== 1 || value.evidence_kind !== 'SIMULATED' || value.run_kind !== expectedRunKind || value.device_gate_decision !== 'UNVERIFIED' || value.d1_go !== false || value.authority_status !== 'AUTHORITY_NOT_ISSUED' || value.physical_camera_access_authorized !== false || value.participant_collection_authorized !== false || value.collection_authorized !== false || value.package_contains_integration !== false || !['PERSISTED', 'NOT_PERSISTED'].includes(String(value.integration_status)) || ![null, 'BACKEND_CONTRACT_PASS', 'NO_GO'].includes(value.d1_outcome as null | string) || typeof value.status !== 'string' || !Number.isSafeInteger(value.observation_count) || Number(value.observation_count) < 0 || !isNullableDigest(value.observation_digest) || !isNullableDigest(value.d1_receipt_digest) || !isDigest(value.result_digest) || !(value.d1_failure_code === null || typeof value.d1_failure_code === 'string') || !(value.integration_failure_code === null || typeof value.integration_failure_code === 'string')) return invalidSyntheticResponse();
  const persisted = value.integration_status === 'PERSISTED';
  if (persisted) {
    if (typeof value.artifact_id !== 'string' || value.artifact_id.length === 0 || !isDigest(value.artifact_sha256) || value.manifest_schema_version !== 2 || !isDigest(value.observation_digest) || !isDigest(value.d1_receipt_digest) || value.integration_failure_code !== null || !['BACKEND_CONTRACT_PASS', 'NO_GO'].includes(String(value.d1_outcome))) return invalidSyntheticResponse();
    if ((value.d1_outcome === 'BACKEND_CONTRACT_PASS' && value.d1_failure_code !== null) || (value.d1_outcome === 'NO_GO' && typeof value.d1_failure_code !== 'string')) return invalidSyntheticResponse();
  } else if (value.artifact_id !== null || value.artifact_sha256 !== null || value.manifest_schema_version !== null || typeof value.integration_failure_code !== 'string') return invalidSyntheticResponse();
  return { schemaVersion: 1, status: value.status, integrationStatus: value.integration_status as SyntheticReviewReceipt['integrationStatus'], evidenceKind: 'SIMULATED', runKind: expectedRunKind, d1Outcome: value.d1_outcome as SyntheticReviewReceipt['d1Outcome'], d1FailureCode: value.d1_failure_code as string | null, integrationFailureCode: value.integration_failure_code as string | null, deviceGateDecision: 'UNVERIFIED', d1Go: false, authorityStatus: 'AUTHORITY_NOT_ISSUED', physicalCameraAccessAuthorized: false, participantCollectionAuthorized: false, collectionAuthorized: false, observationCount: value.observation_count as number, observationDigest: value.observation_digest, d1ReceiptDigest: value.d1_receipt_digest, artifactId: value.artifact_id as string | null, artifactSha256: value.artifact_sha256 as string | null, manifestSchemaVersion: value.manifest_schema_version as 2 | null, packageContainsIntegration: false, resultDigest: value.result_digest };
};
const mapSyntheticRun = (value: unknown): SyntheticReviewRun => {
  if (!isRecord(value) || !exactKeys(value, syntheticRecordKeys) || value.schema_version !== 1 || typeof value.request_id !== 'string' || !/^synrun-[0-9a-f]{32}$/.test(value.request_id) || !Number.isSafeInteger(value.run_sequence) || Number(value.run_sequence) < 1 || !['PREFLIGHT_60S', 'NOMINAL_20M'].includes(String(value.run_kind)) || !['QUEUED', 'RUNNING', 'TERMINAL'].includes(String(value.job_status)) || !(value.service_failure_code === null || typeof value.service_failure_code === 'string')) return invalidSyntheticResponse();
  const terminal = value.job_status === 'TERMINAL'; if ((!terminal && value.receipt !== null) || (terminal && value.receipt === null && value.service_failure_code === null)) return invalidSyntheticResponse();
  const runKind = value.run_kind as SyntheticReviewRunKind;
  return { schemaVersion: 1, requestId: value.request_id, runSequence: value.run_sequence as number, runKind, jobStatus: value.job_status as SyntheticReviewRun['jobStatus'], serviceFailureCode: value.service_failure_code as string | null, receipt: value.receipt === null ? null : mapSyntheticReceipt(value.receipt, runKind) };
};
const mapSyntheticRunEnvelope = (value: unknown): SyntheticReviewRun => {
  if (!isRecord(value) || !exactKeys(value, [...syntheticAuthorityKeys, 'run']) || !hasClosedSyntheticAuthority(value)) return invalidSyntheticResponse();
  return mapSyntheticRun(value.run);
};
const syntheticEvidenceStatus = 'M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY';
const syntheticEvidenceKeys = ['artifact_kind', 'body', 'body_sha256', 'schema_version', 'status'] as const;
const syntheticEvidenceBodyKeys = ['authority_ceiling', 'export_authority_effect', 'export_mode', 'source_artifact', 'source_artifact_byte_size', 'source_artifact_sha256', 'source_run'] as const;
const syntheticEvidencePrefix = '{"artifact_kind":"M2_SYNTHETIC_EVIDENCE_BUNDLE","body":';
const rawSyntheticEvidenceBody = (decoded: string, bodySha256: string): string => {
  const suffix = `,"body_sha256":"${bodySha256}","schema_version":1,"status":"${syntheticEvidenceStatus}"}\n`;
  if (!decoded.startsWith(syntheticEvidencePrefix) || !decoded.endsWith(suffix)) return invalidSyntheticResponse();
  const body = decoded.slice(syntheticEvidencePrefix.length, -suffix.length);
  if (!body.startsWith('{') || !body.endsWith('}')) return invalidSyntheticResponse();
  return body;
};
const sha256Bytes = async (bytes: Uint8Array): Promise<string> => {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))).map((value) => value.toString(16).padStart(2, '0')).join('');
};
const validateSyntheticEvidence = (value: unknown, requestId: string): void => {
  if (!isRecord(value) || !exactKeys(value, syntheticEvidenceKeys) || value.artifact_kind !== 'M2_SYNTHETIC_EVIDENCE_BUNDLE' || value.schema_version !== 1 || value.status !== syntheticEvidenceStatus || !isDigest(value.body_sha256) || !isRecord(value.body) || !exactKeys(value.body, syntheticEvidenceBodyKeys)) return invalidSyntheticResponse();
  const body = value.body;
  if (!isRecord(body.authority_ceiling) || !exactKeys(body.authority_ceiling, syntheticAuthorityKeys) || !hasClosedSyntheticAuthority(body.authority_ceiling) || body.export_authority_effect !== 'NONE' || body.export_mode !== 'DOWNLOAD_ONLY_NO_SERVER_ARCHIVE' || !isRecord(body.source_artifact) || !Number.isSafeInteger(body.source_artifact_byte_size) || Number(body.source_artifact_byte_size) < 2 || Number(body.source_artifact_byte_size) > 4_000_000 || !isDigest(body.source_artifact_sha256) || !isRecord(body.source_run) || body.source_run.request_id !== requestId) return invalidSyntheticResponse();
};
const invalidSyntheticEvidenceDownload = (): never => { throw new Error('Synthetic evidence download is invalid'); };
const invalidResearchResponse = () => { throw new Error('Research API response is invalid'); };
const hasResearchSchema = (value: unknown): value is Record<string, unknown> => isRecord(value) && value.schema_version === 1;
const mapResearchStudy = (value: unknown, studyCode: string): ResearchStudy => {
  if (!hasResearchSchema(value) || typeof value.study_id !== 'string' || value.status !== 'APPROVAL_PENDING') return invalidResearchResponse();
  return { id: value.study_id, studyCode };
};
const mapResearchParticipant = (value: unknown): ResearchParticipant => {
  if (!hasResearchSchema(value) || typeof value.participant_id !== 'string' || typeof value.participant_pseudonym !== 'string') return invalidResearchResponse();
  return { id: value.participant_id, pseudonym: value.participant_pseudonym };
};
const mapCreatedResearchSession = (value: unknown): ResearchSession => {
  if (!hasResearchSchema(value) || typeof value.session_id !== 'string' || value.session_kind !== 'RESEARCH' || value.state !== 'DRAFT' || typeof value.participant_pseudonym !== 'string') return invalidResearchResponse();
  return { id: value.session_id, participantPseudonym: value.participant_pseudonym, state: value.state };
};
const mapConsentConfirmation = (value: unknown, sessionId: string): ResearchSession => {
  if (!hasResearchSchema(value) || value.session_id !== sessionId || value.consent_confirmed !== true) return invalidResearchResponse();
  return { id: value.session_id, state: 'CONSENT_CONFIRMED' };
};
const mapResearchReadiness = (value: unknown): ResearchReadiness => {
  if (!hasResearchSchema(value) || typeof value.ready !== 'boolean' || !isStringArray(value.blocking_gates)) return invalidResearchResponse();
  return { ready: value.ready, blockingGates: value.blocking_gates };
};
const mapResearchRecovery = (value: unknown, requestedSessionId: string): ResearchRecovery => {
  if (!hasResearchSchema(value) || value.session_id !== requestedSessionId || !isSessionState(value.state) || typeof value.collection_blocked !== 'boolean' || typeof value.reauthentication_required !== 'boolean') return invalidResearchResponse();
  return { sessionId: value.session_id, state: value.state, collectionBlocked: value.collection_blocked, reauthenticationRequired: value.reauthentication_required };
};
const mapWithdrawalStatus = (value: unknown): WithdrawalStatus => {
  if (!hasResearchSchema(value) || typeof value.participant_pseudonym !== 'string' || (typeof value.withdrawal_receipt_id !== 'string' && value.withdrawal_receipt_id !== null) || typeof value.terminal !== 'boolean' || typeof value.task_count !== 'number') return invalidResearchResponse();
  return { participantPseudonym: value.participant_pseudonym, withdrawalReceiptId: value.withdrawal_receipt_id, terminal: value.terminal, taskCount: value.task_count };
};
const mapReconciliationPlan = (value: unknown): ReconciliationPlan => {
  if (!isRecord(value) || value.operational_ledger_version !== 3 || value.plan_schema_version !== 1 || typeof value.participant_pseudonym !== 'string' || typeof value.plan_sha256 !== 'string' || value.plan_sha256.length !== 64 || typeof value.confirmation_phrase !== 'string' || typeof value.local_target_total !== 'number' || typeof value.external_target_total !== 'number' || typeof value.blocked_target_total !== 'number' || typeof value.recovery_required_total !== 'number' || typeof value.complete !== 'boolean' || !isStringArray(value.blocker_codes) || !Array.isArray(value.targets)) return invalidResearchResponse();
  const targets = value.targets.map((target) => {
    if (!isRecord(target) || typeof target.target_id !== 'string' || !['LOCAL_RESEARCH_FILE', 'LOCAL_EXPORT_STAGING_FILE', 'EXTERNAL_COPY'].includes(String(target.target_kind)) || typeof target.state !== 'string') return invalidResearchResponse();
    return { targetId: target.target_id, targetKind: target.target_kind as ReconciliationTarget['targetKind'], state: target.state };
  });
  return { participantPseudonym: value.participant_pseudonym, planSha256: value.plan_sha256, confirmationPhrase: value.confirmation_phrase, localTargetTotal: value.local_target_total, externalTargetTotal: value.external_target_total, blockedTargetTotal: value.blocked_target_total, recoveryRequiredTotal: value.recovery_required_total, complete: value.complete, blockerCodes: value.blocker_codes, targets };
};
const mapReconciliationChallenge = (value: unknown): ReconciliationChallenge => {
  if (!isRecord(value) || typeof value.challenge_id !== 'string' || typeof value.challenge_token !== 'string' || typeof value.plan_sha256 !== 'string' || typeof value.confirmation_phrase !== 'string' || typeof value.expires_at !== 'number') return invalidResearchResponse();
  return { challengeId: value.challenge_id, challengeToken: value.challenge_token, planSha256: value.plan_sha256, confirmationPhrase: value.confirmation_phrase, expiresAt: value.expires_at };
};

function clearReviewerSession(): void {
  try {
    window.sessionStorage.removeItem(reviewerStorageKey);
  } catch {
    // The browser storage boundary is unavailable; callers remain signed out.
  }
}

function readReviewerSession(): StoredReviewerSession | undefined {
  let raw: string | null;
  try {
    raw = window.sessionStorage.getItem(reviewerStorageKey);
  } catch {
    return undefined;
  }
  if (raw === null) return undefined;
  try {
    const candidate = JSON.parse(raw) as Partial<StoredReviewerSession>;
    if (
      candidate.schemaVersion !== 1 ||
      typeof candidate.accessToken !== 'string' ||
      typeof candidate.expiresAtUtc !== 'string' ||
      typeof candidate.reviewer !== 'string'
    ) {
      clearReviewerSession();
      return undefined;
    }
    return candidate as StoredReviewerSession;
  } catch {
    clearReviewerSession();
    return undefined;
  }
}

function requestHeaders(headers?: HeadersInit): Record<string, string> {
  if (headers === undefined) return {};
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  if (Array.isArray(headers)) return Object.fromEntries(headers);
  return { ...headers };
}

export interface ApiClient {
  health(): Promise<Health>;
  login(pin: string): Promise<{ reviewer: string }>;
  reviewerSession(): Promise<{ reviewer: string }>;
  logout(): Promise<void>;
  createSession(): Promise<{ id: string; pairingCode: string; snapshot: SessionSnapshot }>;
  pair(pairingCode: string): Promise<{ sessionId: string }>;
  consent(sessionId: string): Promise<SessionSnapshot>;
  preflight(sessionId: string): Promise<SessionSnapshot>;
  start(sessionId: string): Promise<SessionSnapshot>;
  stop(sessionId: string): Promise<SessionSnapshot>;
  status(): Promise<SessionSnapshot>;
  answer(answer: AnswerIntent, idempotencyKey: string): Promise<{ accepted: boolean }>;
  submit(idempotencyKey: string): Promise<{ submitted: boolean }>;
  snapshot(sessionId: string): Promise<SessionSnapshot>;
  events(sessionId: string): Promise<ReviewerEvent[]>;
  replay(sessionId: string): Promise<void>;
}

export interface ResearchApi {
  createStudy(studyCode: string, idempotencyKey: string): Promise<ResearchStudy>;
  createParticipant(studyId: string, idempotencyKey: string): Promise<ResearchParticipant>;
  createResearchSession(input: ResearchSessionIntent, idempotencyKey: string): Promise<ResearchSession>;
  confirmResearchConsent(sessionId: string, input: ConsentConfirmationIntent, idempotencyKey: string): Promise<ResearchSession>;
  readiness(sessionId: string): Promise<ResearchReadiness>;
  getRecovery(sessionId: string): Promise<ResearchRecovery>;
  withdraw(sessionId: string, idempotencyKey: string): Promise<WithdrawalStatus>;
  withdrawalStatus(sessionId: string): Promise<WithdrawalStatus>;
  reconciliation?(sessionId: string): Promise<ReconciliationPlan>;
  createReconciliationChallenge?(sessionId: string, pin: string, action: 'EXECUTE_LOCAL_RECONCILIATION' | 'ATTEST_EXTERNAL_DELETION', targetId?: string): Promise<ReconciliationChallenge>;
  executeReconciliation?(sessionId: string, challengeToken: string, confirmationPhrase: string): Promise<void>;
}

export interface SyntheticReviewApi {
  createSyntheticRun(runKind: SyntheticReviewRunKind, idempotencyKey: string): Promise<SyntheticReviewRun>;
  listSyntheticRuns(): Promise<SyntheticReviewRun[]>;
  getSyntheticRun(requestId: string): Promise<SyntheticReviewRun>;
  downloadSyntheticEvidence(requestId: string): Promise<SyntheticEvidenceDownload>;
}
export const isSyntheticReviewApi = (value: unknown): value is SyntheticReviewApi => isRecord(value) && typeof value.createSyntheticRun === 'function' && typeof value.listSyntheticRuns === 'function' && typeof value.getSyntheticRun === 'function' && typeof value.downloadSyntheticEvidence === 'function';

export interface ReviewerAuthLossSource { onReviewerAuthLoss(listener: () => void): () => void; }
export const isReviewerAuthLossSource = (value: ApiClient): value is ApiClient & ReviewerAuthLossSource => typeof (value as Partial<ReviewerAuthLossSource>).onReviewerAuthLoss === 'function';

export interface EventStream {
  subscribe(
    onMessage: (message: StreamMessage) => void,
    onStatus: (status: 'connected' | 'reconnecting') => void,
    onAuthLoss?: () => void,
  ): () => void;
}

export class HttpApiClient implements ApiClient, ResearchApi, SyntheticReviewApi, ReviewerAuthLossSource {
  private readonly authLossListeners = new Set<() => void>();
  private authLossNotified = false;
  constructor(private readonly surface: ApiSurface = window.location.pathname === '/monitor' ? 'monitor' : 'exam') {}

  private async requestResponse(
    path: string,
    init: RequestInit = {},
    reviewerAuth = false,
    tokenOverride?: string,
  ): Promise<Response> {
    const headers = requestHeaders(init.headers);
    let credentials: RequestCredentials;
    if (this.surface === 'monitor') {
      const session = reviewerAuth && tokenOverride === undefined ? readReviewerSession() : undefined;
      const accessToken = tokenOverride ?? session?.accessToken;
      if (reviewerAuth && accessToken === undefined) {
        clearReviewerSession();
        throw new ApiError(401);
      }
      if (accessToken !== undefined) headers.Authorization = `Bearer ${accessToken}`;
      credentials = 'omit';
    } else {
      const csrf = readCookie('pdu_exam_csrf');
      if (csrf !== undefined) headers['X-CSRF-Token'] = decodeURIComponent(csrf);
      credentials = 'include';
    }
    if (init.body !== undefined) headers['Content-Type'] = 'application/json';

    const response = await fetch(`/api/v1${path}`, { ...init, credentials, headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => undefined) as { code?: string; message?: string; detail?: { code?: string; message?: string } | string } | undefined;
      const retryAfter = Number(response.headers.get('Retry-After'));
      const detail = payload?.message ?? (typeof payload?.detail === 'string' ? payload.detail : payload?.detail?.message);
      if (this.surface === 'monitor' && response.status === 401) {
        clearReviewerSession();
        if (!this.authLossNotified) {
          this.authLossNotified = true;
          for (const listener of this.authLossListeners) listener();
        }
      }
      throw new ApiError(
        response.status,
        Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined,
        payload?.code ?? (typeof payload?.detail === 'string' ? undefined : payload?.detail?.code),
        detail,
      );
    }
    return response;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    reviewerAuth = false,
    tokenOverride?: string,
  ): Promise<T> {
    const response = await this.requestResponse(path, init, reviewerAuth, tokenOverride);
    return response.status === 204 ? undefined as T : response.json() as Promise<T>;
  }

  onReviewerAuthLoss(listener: () => void): () => void {
    this.authLossListeners.add(listener);
    return () => this.authLossListeners.delete(listener);
  }

  async health(): Promise<Health> {
    const payload = await this.request<{ schema_version: number; status: 'ok' }>('/health');
    return { schemaVersion: payload.schema_version, status: payload.status };
  }

  async login(pin: string): Promise<{ reviewer: string }> {
    const payload = await this.request<BackendReviewerLogin>('/reviewer/login', {
      method: 'POST',
      body: JSON.stringify({ pin }),
    });
    if (
      payload.schema_version !== 1 ||
      payload.token_type !== 'Bearer' ||
      typeof payload.access_token !== 'string' ||
      typeof payload.expires_at_utc !== 'string' ||
      typeof payload.reviewer !== 'string'
    ) {
      throw new Error('Reviewer login response is invalid');
    }
    try {
      window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
        schemaVersion: 1,
        accessToken: payload.access_token,
        expiresAtUtc: payload.expires_at_utc,
        reviewer: payload.reviewer,
      } satisfies StoredReviewerSession));
      this.authLossNotified = false;
    } catch {
      clearReviewerSession();
      try {
        await this.request<void>('/reviewer/logout', { method: 'POST' }, true, payload.access_token);
      } catch {
        // A best-effort revoke cannot safely make storage available.
      }
      throw new Error('Reviewer session storage is unavailable');
    }
    return { reviewer: payload.reviewer };
  }

  async reviewerSession(): Promise<{ reviewer: string }> {
    const payload = await this.request<BackendReviewerSession>('/reviewer/session', {}, true);
    if (payload.schema_version !== 1 || typeof payload.reviewer !== 'string') {
      clearReviewerSession();
      throw new ApiError(401);
    }
    return { reviewer: payload.reviewer };
  }

  async logout(): Promise<void> {
    try {
      await this.request<void>('/reviewer/logout', { method: 'POST' }, true);
    } finally {
      if (this.surface === 'monitor') clearReviewerSession();
    }
  }

  async createSession(): Promise<{ id: string; pairingCode: string; snapshot: SessionSnapshot }> {
    const payload = await this.request<{ session_id: string; pairing_code: string }>('/sessions', { method: 'POST' }, true);
    return { id: payload.session_id, pairingCode: payload.pairing_code, snapshot: await this.snapshot(payload.session_id) };
  }

  async pair(pairingCode: string): Promise<{ sessionId: string }> {
    const payload = await this.request<{ session_id: string }>('/candidate/pair', {
      method: 'POST',
      body: JSON.stringify({ pairing_code: pairingCode }),
    });
    return { sessionId: payload.session_id };
  }

  private action(
    sessionId: string,
    action: 'consent' | 'preflight' | 'start' | 'stop',
    reviewerAuth: boolean,
  ): Promise<SessionSnapshot> {
    return this.request<BackendSnapshot>(
      `/sessions/${encodeURIComponent(sessionId)}/${action}`,
      { method: 'POST' },
      reviewerAuth,
    ).then(mapSnapshot);
  }

  consent(sessionId: string): Promise<SessionSnapshot> { return this.action(sessionId, 'consent', false); }
  preflight(sessionId: string): Promise<SessionSnapshot> { return this.action(sessionId, 'preflight', false); }
  start(sessionId: string): Promise<SessionSnapshot> { return this.action(sessionId, 'start', true); }
  stop(sessionId: string): Promise<SessionSnapshot> { return this.action(sessionId, 'stop', true); }

  async status(): Promise<SessionSnapshot> {
    return mapSnapshot(await this.request<BackendSnapshot>('/exam/status'));
  }

  answer(answer: AnswerIntent, idempotencyKey: string): Promise<{ accepted: boolean }> {
    return this.request<{ schema_version: number; accepted: boolean }>('/exam/answers', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ answer_id: answer.answerId, question_id: answer.questionId, value: answer.value }),
    }).then(({ accepted }) => ({ accepted }));
  }

  submit(idempotencyKey: string): Promise<{ submitted: boolean }> {
    return this.request<{ schema_version: number; submitted: boolean }>('/exam/submit', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
    }).then(({ submitted }) => ({ submitted }));
  }

  async snapshot(sessionId: string): Promise<SessionSnapshot> {
    return mapSnapshot(await this.request<BackendSnapshot>(`/sessions/${encodeURIComponent(sessionId)}/snapshot`, {}, true));
  }

  async events(sessionId: string): Promise<ReviewerEvent[]> {
    const payload = await this.request<{ events: BackendEvent[] }>(`/events?session_id=${encodeURIComponent(sessionId)}`, {}, true);
    return payload.events.map(mapEvent).filter((event): event is ReviewerEvent => event !== undefined);
  }

  async replay(sessionId: string): Promise<void> {
    await this.request('/demo/replay', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }, true);
  }

  async createSyntheticRun(runKind: SyntheticReviewRunKind, idempotencyKey: string): Promise<SyntheticReviewRun> { return mapSyntheticRunEnvelope(await this.request<unknown>('/synthetic-runs', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ run_kind: runKind }) }, true)); }
  async listSyntheticRuns(): Promise<SyntheticReviewRun[]> { const value = await this.request<unknown>('/synthetic-runs', {}, true); if (!isRecord(value) || !exactKeys(value, [...syntheticAuthorityKeys, 'runs']) || !hasClosedSyntheticAuthority(value) || !Array.isArray(value.runs)) return invalidSyntheticResponse(); return value.runs.map(mapSyntheticRun); }
  async getSyntheticRun(requestId: string): Promise<SyntheticReviewRun> { return mapSyntheticRunEnvelope(await this.request<unknown>(`/synthetic-runs/${encodeURIComponent(requestId)}`, {}, true)); }
  async downloadSyntheticEvidence(requestId: string): Promise<SyntheticEvidenceDownload> {
    if (!/^synrun-[0-9a-f]{32}$/.test(requestId)) return invalidSyntheticEvidenceDownload();
    const response = await this.requestResponse(`/synthetic-runs/${encodeURIComponent(requestId)}/evidence`, {}, true);
    const expectedFilename = `m2-s2d-${requestId}.json`;
    if (
      response.headers.get('Content-Type') !== 'application/json' ||
      response.headers.get('Content-Disposition') !== `attachment; filename="${expectedFilename}"` ||
      response.headers.get('Cache-Control') !== 'no-store'
    ) return invalidSyntheticEvidenceDownload();
    const expectedDigest = response.headers.get('X-PDU-Evidence-SHA256');
    const declaredLength = Number(response.headers.get('Content-Length'));
    if (!isDigest(expectedDigest) || (Number.isFinite(declaredLength) && declaredLength > 4_000_000)) return invalidSyntheticEvidenceDownload();
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length < 2 || bytes.length > 4_000_000 || await sha256Bytes(bytes) !== expectedDigest) return invalidSyntheticEvidenceDownload();
    let decoded: string;
    let value: unknown;
    try {
      decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      value = JSON.parse(decoded) as unknown;
    } catch {
      return invalidSyntheticEvidenceDownload();
    }
    try {
      validateSyntheticEvidence(value, requestId);
      const bodySha256 = (value as Record<string, unknown>).body_sha256 as string;
      const rawBody = rawSyntheticEvidenceBody(decoded, bodySha256);
      if (await sha256Bytes(new TextEncoder().encode(rawBody)) !== bodySha256) return invalidSyntheticEvidenceDownload();
    } catch {
      return invalidSyntheticEvidenceDownload();
    }
    return { bytes, filename: expectedFilename, sha256: expectedDigest };
  }

  async createStudy(studyCode: string, idempotencyKey: string): Promise<ResearchStudy> { return mapResearchStudy(await this.request<unknown>('/research/studies', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ study_code: studyCode }) }, true), studyCode); }
  async createParticipant(studyId: string, idempotencyKey: string): Promise<ResearchParticipant> { return mapResearchParticipant(await this.request<unknown>('/research/participants', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ study_id: studyId }) }, true)); }
  async createResearchSession(input: ResearchSessionIntent, idempotencyKey: string): Promise<ResearchSession> {
    if (input.retentionPolicyReference !== undefined && input.retentionEndDate !== undefined) throw new Error('Only one retention decision may be sent');
    const payload = { study_id: input.studyId, participant_id: input.participantId, ...(input.retentionPolicyReference !== undefined ? { retention_policy_reference: input.retentionPolicyReference } : {}), ...(input.retentionEndDate !== undefined ? { retention_end_date: input.retentionEndDate } : {}) };
    return mapCreatedResearchSession(await this.request<unknown>('/research/sessions', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) }, true));
  }
  async confirmResearchConsent(sessionId: string, input: ConsentConfirmationIntent, idempotencyKey: string): Promise<ResearchSession> { return mapConsentConfirmation(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/consent-confirmation`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ consent_receipt_id: input.consentReceiptId, consent_version: input.consentVersion }) }, true), sessionId); }
  async readiness(sessionId: string): Promise<ResearchReadiness> { return mapResearchReadiness(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/readiness`, {}, true)); }
  async getRecovery(sessionId: string): Promise<ResearchRecovery> { return mapResearchRecovery(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/recovery`, {}, true), sessionId); }
  async withdraw(sessionId: string, idempotencyKey: string): Promise<WithdrawalStatus> { return mapWithdrawalStatus(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/withdrawal`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } }, true)); }
  async withdrawalStatus(sessionId: string): Promise<WithdrawalStatus> { return mapWithdrawalStatus(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/withdrawal-status`, {}, true)); }
  async reconciliation(sessionId: string): Promise<ReconciliationPlan> { return mapReconciliationPlan(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/reconciliation`, {}, true)); }
  async createReconciliationChallenge(sessionId: string, pin: string, action: 'EXECUTE_LOCAL_RECONCILIATION' | 'ATTEST_EXTERNAL_DELETION', targetId?: string): Promise<ReconciliationChallenge> { return mapReconciliationChallenge(await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/reconciliation/challenges`, { method: 'POST', body: JSON.stringify({ pin, action, target_id: targetId ?? null }) }, true)); }
  async executeReconciliation(sessionId: string, challengeToken: string, confirmationPhrase: string): Promise<void> { await this.request<unknown>(`/research/sessions/${encodeURIComponent(sessionId)}/reconciliation/executions`, { method: 'POST', body: JSON.stringify({ challenge_token: challengeToken, confirmation_phrase: confirmationPhrase }) }, true); }
}

export class DemoApiClient implements ApiClient, ResearchApi {
  private state: SessionState = 'DRAFT';
  private submitted = false;
  private reviewerLoggedIn = false;

  private currentSnapshot(): SessionSnapshot {
    return {
      sessionId: 'DEMO-20260824',
      eventSeq: 0,
      state: this.state,
      submitted: this.submitted,
      durationSeconds: 2700,
      remainingSeconds: this.state === 'RECORDING' ? 2700 : null,
      startedAtUtc: this.state === 'RECORDING' ? new Date().toISOString() : null,
    };
  }

  async health(): Promise<Health> { return { schemaVersion: 1, status: 'ok' }; }
  async login(pin: string): Promise<{ reviewer: string }> { if (!pin) throw new ApiError(401); this.reviewerLoggedIn = true; return { reviewer: 'Nghi\u00ean c\u1ee9u vi\u00ean (demo)' }; }
  async reviewerSession(): Promise<{ reviewer: string }> { if (!this.reviewerLoggedIn) throw new ApiError(401); return { reviewer: 'Nghi\u00ean c\u1ee9u vi\u00ean (demo)' }; }
  async logout(): Promise<void> { this.reviewerLoggedIn = false; }
  async createSession(): Promise<{ id: string; pairingCode: string; snapshot: SessionSnapshot }> { return { id: 'DEMO-20260824', pairingCode: 'DEMO-248', snapshot: this.currentSnapshot() }; }
  async pair(): Promise<{ sessionId: string }> { return { sessionId: 'DEMO-20260824' }; }
  async consent(): Promise<SessionSnapshot> { this.state = 'CONSENT_CONFIRMED'; return this.currentSnapshot(); }
  async preflight(): Promise<SessionSnapshot> { this.state = 'PREFLIGHT_READY'; return this.currentSnapshot(); }
  async start(): Promise<SessionSnapshot> { this.state = 'RECORDING'; return this.currentSnapshot(); }
  async stop(): Promise<SessionSnapshot> { this.state = 'SEALED'; return this.currentSnapshot(); }
  async status(): Promise<SessionSnapshot> { return this.currentSnapshot(); }
  async answer(): Promise<{ accepted: boolean }> { return { accepted: true }; }
  async submit(): Promise<{ submitted: boolean }> { this.submitted = true; return { submitted: true }; }
  async snapshot(): Promise<SessionSnapshot> { return this.currentSnapshot(); }
  async events(): Promise<ReviewerEvent[]> { return []; }
  async replay(): Promise<void> {}
  async createStudy(): Promise<ResearchStudy> { throw new ApiError(404); }
  async createParticipant(): Promise<ResearchParticipant> { throw new ApiError(404); }
  async createResearchSession(): Promise<ResearchSession> { throw new ApiError(404); }
  async confirmResearchConsent(): Promise<ResearchSession> { throw new ApiError(404); }
  async readiness(): Promise<ResearchReadiness> { throw new ApiError(404); }
  async getRecovery(): Promise<ResearchRecovery> { throw new ApiError(404); }
  async withdraw(): Promise<WithdrawalStatus> { throw new ApiError(404); }
  async withdrawalStatus(): Promise<WithdrawalStatus> { throw new ApiError(404); }
}

type ParsedSseMessage = { data: string; id?: string };

class SseParser {
  private buffer = '';
  private dataLines: string[] = [];
  private eventId: string | undefined;

  push(chunk: string): ParsedSseMessage[] {
    this.buffer += chunk;
    const messages: ParsedSseMessage[] = [];
    while (true) {
      const newline = this.buffer.indexOf('\n');
      if (newline < 0) return messages;
      let line = this.buffer.slice(0, newline);
      this.buffer = this.buffer.slice(newline + 1);
      if (line.endsWith('\r')) line = line.slice(0, -1);
      if (line === '') {
        if (this.dataLines.length > 0) {
          messages.push({ data: this.dataLines.join('\n'), id: this.eventId });
          this.dataLines = [];
        }
        continue;
      }
      if (line.startsWith(':')) continue;
      const separator = line.indexOf(':');
      const field = separator < 0 ? line : line.slice(0, separator);
      let value = separator < 0 ? '' : line.slice(separator + 1);
      if (value.startsWith(' ')) value = value.slice(1);
      if (field === 'data') this.dataLines.push(value);
      if (field === 'id' && !value.includes('\u0000')) this.eventId = value;
    }
  }
}

export class BrowserEventStream implements EventStream {
  constructor(private readonly sessionId: string) {}

  subscribe(
    onMessage: (message: StreamMessage) => void,
    onStatus: (status: 'connected' | 'reconnecting') => void,
    onAuthLoss: () => void = () => undefined,
  ): () => void {
    const received = new Set<number>();
    const controller = new AbortController();
    let afterEventSeq = 0;
    let stopped = false;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let reconnectTimer: number | undefined;

    const stopForAuthLoss = (): void => {
      clearReviewerSession();
      onAuthLoss();
    };
    const handleMessage = (message: ParsedSseMessage): void => {
      try {
        const payload = JSON.parse(message.data) as BackendEvent;
        if (isSnapshot(payload)) {
          onMessage({ kind: 'snapshot', snapshot: mapSnapshot(payload) });
          return;
        }
        const event = mapEvent(payload);
        if (event === undefined) return;
        const parsedId = message.id === undefined ? Number.NaN : Number(message.id);
        const sequence = Number.isSafeInteger(parsedId) ? parsedId : event.eventSeq;
        if (received.has(sequence)) return;
        received.add(sequence);
        afterEventSeq = Math.max(afterEventSeq, sequence);
        onMessage({ kind: 'event', event });
      } catch {
        onStatus('reconnecting');
      }
    };
    const waitToReconnect = (delay: number): Promise<void> => new Promise((resolve) => {
      reconnectTimer = window.setTimeout(resolve, delay);
    });
    const run = async (): Promise<void> => {
      let reconnects = 0;
      while (!stopped && reconnects <= maxReconnectAttempts) {
        const session = readReviewerSession();
        if (session === undefined) {
          stopForAuthLoss();
          return;
        }
        try {
          const response = await fetch('/api/v1/events/stream', {
            method: 'POST',
            credentials: 'omit',
            headers: {
              Accept: 'text/event-stream',
              Authorization: `Bearer ${session.accessToken}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ session_id: this.sessionId, after_event_seq: afterEventSeq }),
            signal: controller.signal,
          });
          if (response.status === 401 || response.status === 403) {
            stopForAuthLoss();
            return;
          }
          if (!response.ok || response.body === null) throw new Error('SSE stream is unavailable');
          onStatus('connected');
          const decoder = new TextDecoder();
          const parser = new SseParser();
          reader = response.body.getReader();
          while (!stopped) {
            const next = await reader.read();
            if (next.done) break;
            for (const message of parser.push(decoder.decode(next.value, { stream: true }))) handleMessage(message);
          }
          for (const message of parser.push(decoder.decode())) handleMessage(message);
          reader = undefined;
          if (stopped) return;
          reconnects += 1;
        } catch {
          reader = undefined;
          if (stopped || controller.signal.aborted) return;
          reconnects += 1;
        }
        if (reconnects > maxReconnectAttempts) return;
        onStatus('reconnecting');
        await waitToReconnect(reconnectDelayMs * reconnects);
      }
    };

    void run();
    return () => {
      stopped = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      controller.abort();
      if (reader !== undefined) void reader.cancel().catch(() => undefined);
    };
  }
}

export const noEventStream: EventStream = { subscribe: () => () => undefined };
