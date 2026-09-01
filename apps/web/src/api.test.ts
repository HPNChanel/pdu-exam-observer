import { waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserEventStream, DemoApiClient, HttpApiClient, isSyntheticReviewApi } from './api';

const reviewerStorageKey = 'pdu-exam-observer.reviewer-session.v1';
const token = 'x'.repeat(43);
const loginPayload = {
  schema_version: 1,
  token_type: 'Bearer',
  access_token: token,
  expires_at_utc: '2023-11-15T00:13:20Z',
  reviewer: 'Nghien cuu vien',
};
const snapshot = {
  session_id: 's-1',
  event_seq: 0,
  submitted: false,
  state: 'DRAFT',
  duration_seconds: 2700,
  remaining_seconds: null,
  started_at_utc: null,
};

const response = (body: unknown, status = 200, headers?: HeadersInit) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });

const evidenceAuthority = {
  authority_status: 'AUTHORITY_NOT_ISSUED',
  capability_status: 'SYNTHETIC_REVIEW_ONLY',
  collection_authorized: false,
  d1_go: false,
  device_gate_decision: 'UNVERIFIED',
  evidence_kind: 'SIMULATED',
  execution_authorized: false,
  package_contains_integration: false,
  participant_collection_authorized: false,
  physical_camera_access_authorized: false,
  production_reconciler_implemented: false,
  production_reconciler_real_storage_verified: false,
  real_data_deletion_authorized: false,
  research_ready: false,
  schema_version: 1,
};

const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (typeof value === 'object' && value !== null) {
    const item = value as Record<string, unknown>;
    return `{${Object.keys(item).sort().map((key) => `${JSON.stringify(key)}:${canonical(item[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
};

const evidenceDocument = (requestId: string) => ({
  artifact_kind: 'M2_SYNTHETIC_EVIDENCE_BUNDLE',
  body: {
    authority_ceiling: evidenceAuthority,
    export_authority_effect: 'NONE',
    export_mode: 'DOWNLOAD_ONLY_NO_SERVER_ARCHIVE',
    source_artifact: {},
    source_artifact_byte_size: 2,
    source_artifact_sha256: 'b'.repeat(64),
    source_run: { request_id: requestId },
  },
  body_sha256: 'c'.repeat(64),
  schema_version: 1,
  status: 'M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY',
});

const sha256 = async (bytes: Uint8Array): Promise<string> => {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))).map((value) => value.toString(16).padStart(2, '0')).join('');
};

async function evidenceResponse(requestId: string, body: unknown = evidenceDocument(requestId), headers: HeadersInit = {}): Promise<Response> {
  const document = body as ReturnType<typeof evidenceDocument>;
  if (document && typeof document === 'object' && document.body && typeof document.body === 'object') {
    document.body_sha256 = await sha256(new TextEncoder().encode(canonical(document.body)));
  }
  const bytes = new TextEncoder().encode(`${canonical(document)}\n`);
  return new Response(bytes, {
    status: 200,
    headers: {
      'Cache-Control': 'no-store',
      'Content-Disposition': `attachment; filename="m2-s2d-${requestId}.json"`,
      'Content-Type': 'application/json',
      'X-PDU-Evidence-SHA256': await sha256(bytes),
      ...headers,
    },
  });
}

function openEventStream(chunks: Uint8Array[], close = false): Response {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(chunk));
        if (close) controller.close();
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe('HTTP API adapter', () => {
  it('persists the login bearer only in versioned tab storage and omits monitor credentials', async () => {
    document.cookie = 'pdu_monitor_csrf=legacy-csrf';
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(loginPayload))
      .mockResolvedValueOnce(response({ session_id: 's-1', pairing_code: 'pair-1' }))
      .mockResolvedValueOnce(response(snapshot));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await api.login('2468');
    const stored = JSON.parse(window.sessionStorage.getItem(reviewerStorageKey) ?? '{}') as Record<string, unknown>;
    await api.createSession();

    expect(stored).toEqual({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/reviewer/login');
    expect((fetchMock.mock.calls[0][1] as RequestInit).credentials).toBe('omit');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/sessions');
    expect((fetchMock.mock.calls[1][1] as RequestInit)).toMatchObject({
      credentials: 'omit',
      headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
    });
    expect((fetchMock.mock.calls[1][1] as RequestInit).headers).not.toHaveProperty('X-CSRF-Token');
  });

  it('keeps candidate cookies and CSRF behavior unchanged', async () => {
    document.cookie = 'pdu_exam_csrf=exam-token';
    const fetchMock = vi.fn().mockResolvedValue(response({ schema_version: 1, accepted: true }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('exam');

    await api.answer({ answerId: 'q1-A', questionId: 'q1', value: 'A' }, 'retry-key');

    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: 'include',
      headers: expect.objectContaining({ 'Idempotency-Key': 'retry-key', 'X-CSRF-Token': 'exam-token' }),
    });
  });

  it('revokes an issued bearer and fails closed when tab storage cannot persist it', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(loginPayload))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota');
    });

    await expect(new HttpApiClient('monitor').login('2468')).rejects.toThrow();

    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/reviewer/logout');
    expect((fetchMock.mock.calls[1][1] as RequestInit)).toMatchObject({
      credentials: 'omit',
      headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
    });
    expect(window.sessionStorage.getItem(reviewerStorageKey)).toBeNull();
  });

  it('clears the tab bearer on monitor 401 and from logout finally', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ detail: 'Reviewer authentication required' }, 401))
      .mockResolvedValueOnce(response({ detail: 'server error' }, 500));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await expect(api.createSession()).rejects.toMatchObject({ status: 401 });
    expect(window.sessionStorage.getItem(reviewerStorageKey)).toBeNull();

    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    await expect(api.logout()).rejects.toMatchObject({ status: 500 });
    expect(window.sessionStorage.getItem(reviewerStorageKey)).toBeNull();
  });

  it('maps the exact create-study response returned by the M1 backend', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      schema_version: 1,
      study_id: 'study-xDE0JVfYgjMt',
      status: 'APPROVAL_PENDING',
    }, 201)));

    await expect(new HttpApiClient('monitor').createStudy('PDU-M1-01', 'study-key')).resolves.toEqual({
      id: 'study-xDE0JVfYgjMt',
      studyCode: 'PDU-M1-01',
    });
  });

  it('maps the exact create-research-session response returned by the M1 backend', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      schema_version: 1,
      session_id: 'research-1',
      session_kind: 'RESEARCH',
      state: 'DRAFT',
      participant_pseudonym: 'p-1',
    }, 201)));

    await expect(new HttpApiClient('monitor').createResearchSession({ studyId: 'study-1', participantId: 'participant-1' }, 'session-key')).resolves.toEqual({
      id: 'research-1',
      participantPseudonym: 'p-1',
      state: 'DRAFT',
    });
  });

  it('maps the exact consent-confirmation response returned by the M1 backend', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      schema_version: 1,
      session_id: 'research-1',
      consent_confirmed: true,
    })));

    await expect(new HttpApiClient('monitor').confirmResearchConsent('research-1', { consentReceiptId: 'receipt-1', consentVersion: 'v1' }, 'consent-key')).resolves.toEqual({
      id: 'research-1',
      state: 'CONSENT_CONFIRMED',
    });
  });

  it('uses the reviewer bearer and omitted credentials for exact M1 recovery reads', async () => {
    const sessionId = 'research-oDUliIaM2hjS_xIg';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghien cuu vien' }));
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ schema_version: 1, session_id: sessionId, state: 'DRAFT', collection_blocked: true, reauthentication_required: true }))
      .mockResolvedValueOnce(response({ schema_version: 1, ready: false, blocking_gates: ['INSTITUTIONAL_APPROVAL_REQUIRED'] }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await expect(api.getRecovery(sessionId)).resolves.toEqual({ sessionId, state: 'DRAFT', collectionBlocked: true, reauthenticationRequired: true });
    await expect(api.readiness(sessionId)).resolves.toEqual({ ready: false, blockingGates: ['INSTITUTIONAL_APPROVAL_REQUIRED'] });

    for (const [index, path] of [`/api/v1/research/sessions/${sessionId}/recovery`, `/api/v1/research/sessions/${sessionId}/readiness`].entries()) {
      const [actualPath, init] = fetchMock.mock.calls[index] as [string, RequestInit];
      expect(actualPath).toBe(path);
      expect(init).toMatchObject({ credentials: 'omit', headers: expect.objectContaining({ Authorization: `Bearer ${token}` }) });
    }
  });

  it('fails closed when a recovery or readiness response is outside schema v1', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghien cuu vien' }));
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ schema_version: 2, session_id: 'research-oDUliIaM2hjS_xIg', state: 'DRAFT', collection_blocked: true, reauthentication_required: true }))
      .mockResolvedValueOnce(response({ schema_version: 1, ready: false, blocking_gates: [42] }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await expect(api.getRecovery('research-oDUliIaM2hjS_xIg')).rejects.toThrow('Research API response is invalid');
    await expect(api.readiness('research-oDUliIaM2hjS_xIg')).rejects.toThrow('Research API response is invalid');
  });

  it('rejects a recovery payload that names a different requested session', async () => {
    const requestedSessionId = 'research-oDUliIaM2hjS_xIg';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghien cuu vien' }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ schema_version: 1, session_id: 'research-otherSessionId_1234', state: 'DRAFT', collection_blocked: true, reauthentication_required: true })));

    await expect(new HttpApiClient('monitor').getRecovery(requestedSessionId)).rejects.toThrow('Research API response is invalid');
  });

  it('sends exact current M1 mutation payloads without legacy fields', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ schema_version: 1, study_id: 'study-1', status: 'APPROVAL_PENDING' }, 201))
      .mockResolvedValueOnce(response({ schema_version: 1, participant_id: 'participant-1', participant_pseudonym: 'p-1' }, 201))
      .mockResolvedValueOnce(response({ schema_version: 1, session_id: 'research-1', session_kind: 'RESEARCH', state: 'DRAFT', participant_pseudonym: 'p-1' }, 201))
      .mockResolvedValueOnce(response({ schema_version: 1, session_id: 'research-1', consent_confirmed: true }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await api.createStudy('PDU-M1-01', 'study-key');
    await api.createParticipant('study-1', 'participant-key');
    await api.createResearchSession({ studyId: 'study-1', participantId: 'participant-1', retentionPolicyReference: 'retention-1' }, 'session-key');
    await api.confirmResearchConsent('research-1', { consentReceiptId: 'receipt-1', consentVersion: 'v1' }, 'consent-key');

    const expected = [
      ['/api/v1/research/studies', { study_code: 'PDU-M1-01' }],
      ['/api/v1/research/participants', { study_id: 'study-1' }],
      ['/api/v1/research/sessions', { study_id: 'study-1', participant_id: 'participant-1', retention_policy_reference: 'retention-1' }],
      ['/api/v1/research/sessions/research-1/consent-confirmation', { consent_receipt_id: 'receipt-1', consent_version: 'v1' }],
    ];
    for (const [index, [url, body]] of expected.entries()) {
      const [actualUrl, init] = fetchMock.mock.calls[index] as [string, RequestInit];
      expect(actualUrl).toBe(url);
      expect(init.method).toBe('POST');
      expect(JSON.parse(String(init.body))).toEqual(body);
    }
  });

  it('rejects a create-session response outside the exact initial contract', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghien cuu vien' }));
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ schema_version: 1, session_id: 'research-1', session_kind: 'RESEARCH', state: 'SEALED', participant_pseudonym: 'p-1' }, 201))
      .mockResolvedValueOnce(response({ schema_version: 1, session_id: 'research-1', session_kind: 'DEMO', state: 'DRAFT', participant_pseudonym: 'p-1' }, 201));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');

    await expect(api.createResearchSession({ studyId: 'study-1', participantId: 'participant-1' }, 'session-sealed')).rejects.toThrow('Research API response is invalid');
    await expect(api.createResearchSession({ studyId: 'study-1', participantId: 'participant-1' }, 'session-demo')).rejects.toThrow('Research API response is invalid');
  });

  it('rejects a consent-confirmation response for a different session', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghien cuu vien' }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ schema_version: 1, session_id: 'research-other', consent_confirmed: true })));

    await expect(new HttpApiClient('monitor').confirmResearchConsent('research-1', { consentReceiptId: 'receipt-1', consentVersion: 'v1' }, 'consent-key')).rejects.toThrow('Research API response is invalid');
  });
});

describe('synthetic reviewer API adapter', () => {
  const authority = {
    schema_version: 1, capability_status: 'SYNTHETIC_REVIEW_ONLY',
    authority_status: 'AUTHORITY_NOT_ISSUED', collection_authorized: false, d1_go: false,
    device_gate_decision: 'UNVERIFIED', evidence_kind: 'SIMULATED', execution_authorized: false,
    package_contains_integration: false, participant_collection_authorized: false,
    physical_camera_access_authorized: false, production_reconciler_implemented: false,
    production_reconciler_real_storage_verified: false, real_data_deletion_authorized: false,
    research_ready: false,
  };
  const run = {
    schema_version: 1, request_id: 'synrun-0123456789abcdef0123456789abcdef',
    run_sequence: 1, run_kind: 'PREFLIGHT_60S', job_status: 'QUEUED',
    service_failure_code: null, receipt: null,
  };
  const digest = 'a'.repeat(64);
  const receipt = {
    artifact_id: 'artifact-synrun-0123456789abcdef0123456789abcdef', artifact_sha256: digest,
    authority_status: 'AUTHORITY_NOT_ISSUED', collection_authorized: false,
    d1_failure_code: null, d1_go: false, d1_outcome: 'BACKEND_CONTRACT_PASS',
    d1_receipt_digest: digest, device_gate_decision: 'UNVERIFIED', evidence_kind: 'SIMULATED',
    integration_failure_code: null, integration_status: 'PERSISTED', manifest_schema_version: 2,
    observation_count: 977, observation_digest: digest, package_contains_integration: false,
    participant_collection_authorized: false, physical_camera_access_authorized: false,
    result_digest: digest, run_kind: 'PREFLIGHT_60S', schema_version: 1,
    status: 'M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY',
  };

  it('uses reviewer bearer, omitted credentials, one fixed body and idempotency header', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const fetchMock = vi.fn().mockResolvedValue(response({ ...authority, run }, 202)); vi.stubGlobal('fetch', fetchMock);
    await new HttpApiClient('monitor').createSyntheticRun('PREFLIGHT_60S', 'synthetic-key-0001');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/synthetic-runs');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'omit', body: JSON.stringify({ run_kind: 'PREFLIGHT_60S' }), headers: expect.objectContaining({ Authorization: `Bearer ${token}`, 'Idempotency-Key': 'synthetic-key-0001' }) });
  });

  it('maps list and get without exposing backend snake case', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({ ...authority, runs: [run] })).mockResolvedValueOnce(response({ ...authority, run })));
    const api = new HttpApiClient('monitor');
    await expect(api.listSyntheticRuns()).resolves.toEqual([expect.objectContaining({ requestId: run.request_id, runKind: 'PREFLIGHT_60S' })]);
    await expect(api.getSyntheticRun(run.request_id)).resolves.toEqual(expect.objectContaining({ requestId: run.request_id }));
  });

  it('rejects unknown fields and forged authority values', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const forged = { ...authority, collection_authorized: true, device_path: 'C:/camera', run };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(forged)));
    await expect(new HttpApiClient('monitor').getSyntheticRun(run.request_id)).rejects.toThrow('Synthetic review API response is invalid');
  });

  it('rejects malformed terminal receipt semantics', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const malformed = [
      { ...receipt, artifact_sha256: 'ABC' },
      { ...receipt, run_kind: 'NOMINAL_20M' },
      { ...receipt, observation_count: -1 },
      { ...receipt, integration_status: 'NOT_PERSISTED', d1_outcome: null, integration_failure_code: 'PERSISTENCE_FAILED' },
    ];
    const fetchMock = vi.fn();
    for (const candidate of malformed) {
      fetchMock.mockResolvedValueOnce(response({ ...authority, run: { ...run, job_status: 'TERMINAL', receipt: candidate } }));
    }
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');
    for (let index = 0; index < malformed.length; index += 1) {
      await expect(api.getSyntheticRun(run.request_id)).rejects.toThrow('Synthetic review API response is invalid');
    }
  });

  it('maps bounded errors and does not fabricate the optional API in demo mode', async () => {
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ code: 'SYNTHETIC_RUN_ALREADY_ACTIVE', message: 'A synthetic review run is already active.' }, 409)));
    await expect(new HttpApiClient('monitor').createSyntheticRun('PREFLIGHT_60S', 'synthetic-key-0001')).rejects.toMatchObject({ status: 409, code: 'SYNTHETIC_RUN_ALREADY_ACTIVE' });
    expect('createSyntheticRun' in new DemoApiClient()).toBe(false);
  });

  it('downloads authenticated evidence with one exact GET and verified bytes', async () => {
    const requestId = 'synrun-0123456789abcdef0123456789abcdef';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const raw = await evidenceResponse(requestId);
    const floatDocument = evidenceDocument(requestId);
    const rawBody = canonical(floatDocument.body).replace('"source_artifact":{}', '"source_artifact":{"encoded_byte_rate":1000000.0}');
    floatDocument.body_sha256 = await sha256(new TextEncoder().encode(rawBody));
    const floatText = `{"artifact_kind":"M2_SYNTHETIC_EVIDENCE_BUNDLE","body":${rawBody},"body_sha256":"${floatDocument.body_sha256}","schema_version":1,"status":"${floatDocument.status}"}\n`;
    const floatBytes = new TextEncoder().encode(floatText);
    const floatResponse = new Response(floatBytes, { status: 200, headers: { 'Cache-Control': 'no-store', 'Content-Disposition': `attachment; filename="m2-s2d-${requestId}.json"`, 'Content-Type': 'application/json', 'X-PDU-Evidence-SHA256': await sha256(floatBytes) } });
    const fetchMock = vi.fn().mockResolvedValueOnce(raw).mockResolvedValueOnce(floatResponse);
    vi.stubGlobal('fetch', fetchMock);

    const downloaded = await new HttpApiClient('monitor').downloadSyntheticEvidence(requestId);

    expect(downloaded.filename).toBe(`m2-s2d-${requestId}.json`);
    expect(downloaded.sha256).toBe(await sha256(downloaded.bytes));
    await expect(new HttpApiClient('monitor').downloadSyntheticEvidence(requestId)).resolves.toMatchObject({ filename: `m2-s2d-${requestId}.json` });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/synthetic-runs/${requestId}/evidence`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'omit', headers: expect.objectContaining({ Authorization: `Bearer ${token}` }) });
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBeUndefined();
  });

  it('rejects forged digest content type disposition and oversized downloads', async () => {
    const requestId = 'synrun-0123456789abcdef0123456789abcdef';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const cases = [
      await evidenceResponse(requestId, evidenceDocument(requestId), { 'X-PDU-Evidence-SHA256': '0'.repeat(64) }),
      await evidenceResponse(requestId, evidenceDocument(requestId), { 'Content-Type': 'text/plain' }),
      await evidenceResponse(requestId, evidenceDocument(requestId), { 'Content-Disposition': 'attachment; filename="C:/private.json"' }),
      new Response(new Uint8Array(4_000_001), { status: 200, headers: { 'Content-Type': 'application/json', 'Content-Disposition': `attachment; filename="m2-s2d-${requestId}.json"`, 'X-PDU-Evidence-SHA256': '0'.repeat(64) } }),
    ];
    const api = new HttpApiClient('monitor');
    for (const item of cases) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(item));
      await expect(api.downloadSyntheticEvidence(requestId)).rejects.toThrow('Synthetic evidence download is invalid');
    }
  });

  it('rejects malformed open and authority-escalated evidence envelopes', async () => {
    const requestId = 'synrun-0123456789abcdef0123456789abcdef';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const open = { ...evidenceDocument(requestId), extra: true };
    const escalated = evidenceDocument(requestId);
    escalated.body.authority_ceiling = { ...evidenceAuthority, research_ready: true };
    const mismatched = evidenceDocument('synrun-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
    const api = new HttpApiClient('monitor');
    for (const body of [open, escalated, mismatched, { malformed: true }]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(await evidenceResponse(requestId, body)));
      await expect(api.downloadSyntheticEvidence(requestId)).rejects.toThrow('Synthetic evidence download is invalid');
    }
  });

  it('applies bounded API errors and one-shot auth loss without retrying download', async () => {
    const requestId = 'synrun-0123456789abcdef0123456789abcdef';
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const fetchMock = vi.fn().mockResolvedValue(response({ code: 'SYNTHETIC_EVIDENCE_NOT_EXPORTABLE', message: 'Synthetic evidence is not exportable for this run.' }, 409));
    vi.stubGlobal('fetch', fetchMock);
    await expect(new HttpApiClient('monitor').downloadSyntheticEvidence(requestId)).rejects.toMatchObject({ status: 409, code: 'SYNTHETIC_EVIDENCE_NOT_EXPORTABLE' });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({ schemaVersion: 1, accessToken: token, expiresAtUtc: '2023-11-15T00:13:20Z', reviewer: 'Nghiên cứu viên' }));
    const authFetch = vi.fn().mockResolvedValue(response({ code: 'AUTHENTICATION_REQUIRED', message: 'Reviewer authentication required.' }, 401));
    vi.stubGlobal('fetch', authFetch);
    const api = new HttpApiClient('monitor');
    const listener = vi.fn();
    api.onReviewerAuthLoss(listener);
    await expect(api.downloadSyntheticEvidence(requestId)).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(authFetch).toHaveBeenCalledTimes(1);
  });

  it('requires the evidence method in the synthetic capability guard', () => {
    const complete = new HttpApiClient('monitor');
    expect(isSyntheticReviewApi(complete)).toBe(true);
    expect(isSyntheticReviewApi({ createSyntheticRun() {}, listSyntheticRuns() {}, getSyntheticRun() {} })).toBe(false);
    expect(isSyntheticReviewApi(new DemoApiClient())).toBe(false);
  });
});

describe('fetch SSE adapter', () => {
  it('parses fragmented UTF-8 CRLF multiline SSE data, ignores comments, and deduplicates ids without EventSource', async () => {
    const encoded = new TextEncoder().encode(
      ': heartbeat\r\n\r\n' +
        `data: ${JSON.stringify({ type: 'SessionSnapshot', ...snapshot })}\r\n\r\n` +
        'id: 4\r\n' +
        'data: {"event_seq":4,"type":"AlertEvent",\r\n' +
        'data: "label":"NO_PERSON","confidence":null,"confidence_status":"INSUFFICIENT","contributing_signals":["d\\u1eef lieu"],"duration_seconds":0}\r\n\r\n' +
        'id: 4\r\n' +
        'data: {"event_seq":4,"type":"AlertEvent","label":"NO_PERSON","confidence":null,"confidence_status":"INSUFFICIENT","contributing_signals":["du lieu"],"duration_seconds":0}\r\n\r\n',
    );
    const nonAscii = encoded.findIndex((value) => value > 127);
    const chunks = nonAscii >= 0
      ? [encoded.slice(0, nonAscii + 1), encoded.slice(nonAscii + 1)]
      : [encoded.slice(0, 7), encoded.slice(7)];
    const fetchMock = vi.fn().mockResolvedValue(openEventStream(chunks));
    vi.stubGlobal('fetch', fetchMock);
    let eventSourceCalls = 0;
    vi.stubGlobal('EventSource', class {
      constructor() { eventSourceCalls += 1; }
    });
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const seen: string[] = [];
    const stop = new BrowserEventStream('s-1').subscribe(
      (message) => seen.push(message.kind === 'snapshot' ? `snapshot:${message.snapshot.state}` : message.event.id),
      () => undefined,
    );

    await waitFor(() => expect(seen).toEqual(['snapshot:DRAFT', 'event-4']));
    stop();

    expect(eventSourceCalls).toBe(0);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/events/stream');
    expect((fetchMock.mock.calls[0][1] as RequestInit)).toMatchObject({
      method: 'POST',
      credentials: 'omit',
      headers: expect.objectContaining({
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({ session_id: 's-1', after_event_seq: 0 }),
    });
  });

  it('delivers the persisted demo replay frames live in monotonic order', async () => {
    const rawReplay = new TextEncoder().encode(
      `data: ${JSON.stringify({ type: 'SessionSnapshot', ...snapshot })}\n\n` +
        'id: 1\n' +
        'data: {"event_seq":1,"type":"DemoEvent","fixture_event_type":"session_started","confidence":null,"confidence_status":"NOT_APPLICABLE","source_kind":"synthetic_demo","payload":{"session_ref":"demo-session-001"}}\n\n' +
        'id: 2\n' +
        'data: {"event_seq":2,"type":"DemoEvent","fixture_event_type":"answer_recorded","confidence":null,"confidence_status":"NOT_APPLICABLE","source_kind":"synthetic_demo","payload":{"question_ref":"q-001","answer_state":"selected"}}\n\n' +
        'id: 3\n' +
        'data: {"event_seq":3,"type":"DemoEvent","fixture_event_type":"technical_state","confidence":null,"confidence_status":"INSUFFICIENT","source_kind":"synthetic_demo","payload":{"reason_code":"DEMO_SIGNAL_UNAVAILABLE"}}\n\n' +
        'id: 4\n' +
        'data: {"event_seq":4,"type":"DemoEvent","fixture_event_type":"session_stopped","confidence":null,"confidence_status":"NOT_APPLICABLE","source_kind":"synthetic_demo","payload":{"stop_reason":"demo_complete"}}\n\n',
    );
    const chunks = [
      rawReplay.slice(0, 91),
      rawReplay.slice(91, 377),
      rawReplay.slice(377, 739),
      rawReplay.slice(739),
    ];
    const fetchMock = vi.fn().mockResolvedValue(openEventStream(chunks));
    vi.stubGlobal('fetch', fetchMock);
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const seen: Array<{ eventSeq: number; confidence: number | null; confidenceStatus: string; signals: string[] }> = [];
    const stop = new BrowserEventStream('s-1').subscribe((message) => {
      if (message.kind === 'event') {
        seen.push({
          eventSeq: message.event.eventSeq,
          confidence: message.event.confidence,
          confidenceStatus: message.event.confidenceStatus,
          signals: message.event.signals,
        });
      }
    }, () => undefined);

    try {
      await waitFor(() => expect(seen).toEqual([
        { eventSeq: 1, confidence: null, confidenceStatus: 'NOT_APPLICABLE', signals: ['synthetic_demo'] },
        { eventSeq: 2, confidence: null, confidenceStatus: 'NOT_APPLICABLE', signals: ['synthetic_demo'] },
        { eventSeq: 3, confidence: null, confidenceStatus: 'INSUFFICIENT', signals: ['synthetic_demo'] },
        { eventSeq: 4, confidence: null, confidenceStatus: 'NOT_APPLICABLE', signals: ['synthetic_demo'] },
      ]));
    } finally {
      stop();
    }
  });

  it('reconnects once after a closed stream and resumes after the last delivered sequence', async () => {
    const first = new TextEncoder().encode(
      'id: 4\ndata: {"event_seq":4,"type":"AlertEvent","label":"NO_PERSON","confidence":null,"confidence_status":"INSUFFICIENT","contributing_signals":[],"duration_seconds":0}\n\n',
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(openEventStream([first], true))
      .mockResolvedValueOnce(openEventStream([]));
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('EventSource', class { close() {} });
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const stop = new BrowserEventStream('s-1').subscribe(() => undefined, () => undefined);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    stop();

    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({
      session_id: 's-1',
      after_event_seq: 4,
    });
  });

  it('bounds reconnects after repeated immediate stream closures', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(openEventStream([], true));
    vi.stubGlobal('fetch', fetchMock);
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const stop = new BrowserEventStream('s-1').subscribe(() => undefined, () => undefined);

    await vi.advanceTimersByTimeAsync(1_000);
    stop();

    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it('aborts without overlapping loops and clears tab auth on a 401 stream response', async () => {
    let signal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise<Response>(() => undefined);
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('EventSource', class { close() {} });
    window.sessionStorage.setItem(reviewerStorageKey, JSON.stringify({
      schemaVersion: 1,
      accessToken: token,
      expiresAtUtc: '2023-11-15T00:13:20Z',
      reviewer: 'Nghien cuu vien',
    }));
    const stop = new BrowserEventStream('s-1').subscribe(() => undefined, () => undefined);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    stop();
    expect(signal?.aborted).toBe(true);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    new BrowserEventStream('s-1').subscribe(() => undefined, () => undefined);
    await waitFor(() => expect(window.sessionStorage.getItem(reviewerStorageKey)).toBeNull());
  });
});
