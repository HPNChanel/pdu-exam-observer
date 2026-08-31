import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ApiError, HttpApiClient } from './api';
import type { ApiClient, ResearchParticipant, ResearchReadiness, ResearchRecovery, ResearchSession, ResearchStudy, WithdrawalStatus } from './api';

type ResearchClient = ApiClient & {
  createStudy(studyCode: string, idempotencyKey: string): Promise<ResearchStudy>;
  createParticipant(studyId: string, idempotencyKey: string): Promise<ResearchParticipant>;
  createResearchSession(input: { studyId: string; participantId: string; retentionPolicyReference?: string; retentionEndDate?: string }, idempotencyKey: string): Promise<ResearchSession>;
  confirmResearchConsent(sessionId: string, input: { consentReceiptId: string; consentVersion: string }, idempotencyKey: string): Promise<ResearchSession>;
  readiness(sessionId: string): Promise<ResearchReadiness>;
  getRecovery(sessionId: string): Promise<ResearchRecovery>;
  withdraw(sessionId: string, idempotencyKey: string): Promise<WithdrawalStatus>;
};

const researchSession: ResearchSession = { id: 'session-h1', studyId: 'study-h1', participantId: 'participant-h1', participantPseudonym: 'PDU-H-001', state: 'DRAFT' };
const readiness: ResearchReadiness = { ready: false, blockingGates: ['INSTITUTIONAL_APPROVAL_REQUIRED'] };
const recovery: ResearchRecovery = { sessionId: researchSession.id, state: 'DRAFT', collectionBlocked: true, reauthenticationRequired: true };
const withdrawal: WithdrawalStatus = { participantPseudonym: 'PDU-H-001', withdrawalReceiptId: 'withdraw-h1', terminal: true, taskCount: 1 };

function makeApi(overrides: Partial<ResearchClient> = {}): ResearchClient {
  const base = {
    health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }), login: vi.fn(), reviewerSession: vi.fn(), logout: vi.fn(), createSession: vi.fn(), pair: vi.fn(), consent: vi.fn(), preflight: vi.fn(), start: vi.fn(), stop: vi.fn(), status: vi.fn(), answer: vi.fn(), submit: vi.fn(), snapshot: vi.fn(), events: vi.fn(), replay: vi.fn(),
  } as unknown as ApiClient;
  return { ...base, createStudy: vi.fn().mockResolvedValue({ id: 'study-h1', studyCode: 'PDU-H-01' }), createParticipant: vi.fn().mockResolvedValue({ id: 'participant-h1', pseudonym: 'PDU-H-001' }), createResearchSession: vi.fn().mockResolvedValue(researchSession), confirmResearchConsent: vi.fn().mockResolvedValue({ ...researchSession, state: 'CONSENT_CONFIRMED' }), readiness: vi.fn().mockResolvedValue(readiness), getRecovery: vi.fn().mockResolvedValue(recovery), withdraw: vi.fn().mockResolvedValue(withdrawal), ...overrides };
}

async function throughSession(api: ResearchClient): Promise<void> {
  render(<App route="/monitor" api={api} initialReviewer />);
  fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-H-01' } });
  fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
  await screen.findByText('PDU-H-01');
  fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
  await screen.findByText('PDU-H-001');
  fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
  await screen.findByText('Phiên nghiên cứu: session-h1');
}

describe('M1 hardening', () => {
  it('returns to the PIN wall when an ordinary research 401 clears the bearer', async () => {
    let notify: (() => void) | undefined;
    const api = makeApi({ createStudy: vi.fn().mockImplementation(async () => { notify?.(); throw new ApiError(401); }) }) as ResearchClient & { onReviewerAuthLoss(listener: () => void): () => void };
    api.onReviewerAuthLoss = (listener) => { notify = listener; return () => { notify = undefined; }; };
    render(<App route="/monitor" api={api} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-H-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    expect(await screen.findByRole('button', { name: 'Mở bàn quan sát' })).toBeInTheDocument();
  });

  it('keeps the research workflow and shows a scoped error for a missing research resource', async () => {
    const api = makeApi({ createStudy: vi.fn().mockRejectedValue(new ApiError(404, undefined, undefined, 'Research study not found')) });
    render(<App route="/monitor" api={api} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-H-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('bản nháp nghiên cứu không còn tồn tại hoặc đã cũ');
    expect(screen.getByRole('region', { name: 'Chuẩn bị nghiên cứu' })).toBeInTheDocument();
    expect(screen.queryByText('Chế độ M1 chưa được bật')).not.toBeInTheDocument();
  });

  it('keeps a stable key for every M1 mutation retry and reports each scoped conflict', async () => {
    const createStudy = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue({ id: 'study-h1', studyCode: 'PDU-H-01' });
    const createParticipant = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue({ id: 'participant-h1', pseudonym: 'PDU-H-001' });
    const createResearchSession = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue(researchSession);
    const confirmResearchConsent = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue({ ...researchSession, state: 'CONSENT_CONFIRMED' });
    const withdraw = vi.fn().mockRejectedValueOnce(new ApiError(409)).mockResolvedValue(withdrawal);
    const api = makeApi({ createStudy, createParticipant, createResearchSession, confirmResearchConsent, withdraw });
    render(<App route="/monitor" api={api} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-H-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('xung đột');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại tạo bản nháp nghiên cứu' }));
    await screen.findByText('PDU-H-01');
    fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại tạo mã giả danh' }));
    await screen.findByText('PDU-H-001');
    fireEvent.change(screen.getByLabelText('Tham chiếu chính sách lưu giữ'), { target: { value: 'retention-h1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-h1');
    fireEvent.change(screen.getByLabelText('Mã biên nhận đồng ý'), { target: { value: 'receipt-h1' } });
    fireEvent.change(screen.getByLabelText('Phiên bản đồng ý'), { target: { value: 'v1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận đồng ý của người đánh giá' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại xác nhận đồng ý' }));
    await waitFor(() => expect(confirmResearchConsent).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận rút khỏi nghiên cứu' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại rút khỏi nghiên cứu' }));
    await screen.findByText('Đã rút khỏi nghiên cứu');
    for (const mutation of [createStudy, createParticipant, createResearchSession, confirmResearchConsent, withdraw]) expect(mutation.mock.calls[1].at(-1)).toBe(mutation.mock.calls[0].at(-1));
    expect(createResearchSession.mock.calls[0][0]).toEqual({ studyId: 'study-h1', participantId: 'participant-h1', retentionPolicyReference: 'retention-h1' });
  });

  it('focuses and restores the terminal-withdrawal dialog trigger, while Escape cancels', async () => {
    const api = makeApi();
    await throughSession(api);
    const trigger = screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' });
    fireEvent.click(trigger);
    const dialog = await screen.findByRole('alertdialog');
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Quay lại' })));
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' })));
  });

  it('rejects a schema-version mismatch and retains monitor auth headers for each mutation', async () => {
    window.sessionStorage.setItem('pdu-exam-observer.reviewer-session.v1', JSON.stringify({ schemaVersion: 1, accessToken: 'bearer-h1', expiresAtUtc: '2026-08-26T00:00:00Z', reviewer: 'R' }));
    const responses = [
      { schema_version: 2, study_id: 'study-h1', status: 'APPROVAL_PENDING' },
      { schema_version: 1, study_id: 'study-h1', status: 'APPROVAL_PENDING' }, { schema_version: 1, study_id: 'study-h1', status: 'APPROVAL_PENDING' },
      { schema_version: 1, participant_id: 'participant-h1', participant_pseudonym: 'PDU-H-001' }, { schema_version: 1, participant_id: 'participant-h1', participant_pseudonym: 'PDU-H-001' },
      { schema_version: 1, session_id: 'session-h1', session_kind: 'RESEARCH', participant_pseudonym: 'PDU-H-001', state: 'DRAFT' }, { schema_version: 1, session_id: 'session-h1', session_kind: 'RESEARCH', participant_pseudonym: 'PDU-H-001', state: 'DRAFT' },
      { schema_version: 1, session_id: 'session-h1', consent_confirmed: true }, { schema_version: 1, session_id: 'session-h1', consent_confirmed: true },
      { schema_version: 1, withdrawal_receipt_id: 'withdraw-h1', participant_pseudonym: 'PDU-H-001', terminal: true, task_count: 1 }, { schema_version: 1, withdrawal_receipt_id: 'withdraw-h1', participant_pseudonym: 'PDU-H-001', terminal: true, task_count: 1 },
    ];
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(responses.shift()), { status: 201, headers: { 'Content-Type': 'application/json' } })));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor');
    await expect(api.createStudy('PDU-H-01', 'study-invalid')).rejects.toThrow('Research API response is invalid');
    await api.createStudy('PDU-H-01', 'study-key'); await api.createStudy('PDU-H-01', 'study-key');
    await api.createParticipant('study-h1', 'participant-key'); await api.createParticipant('study-h1', 'participant-key');
    await api.createResearchSession({ studyId: 'study-h1', participantId: 'participant-h1', retentionPolicyReference: 'retention-h1' }, 'session-key'); await api.createResearchSession({ studyId: 'study-h1', participantId: 'participant-h1', retentionPolicyReference: 'retention-h1' }, 'session-key');
    await api.confirmResearchConsent('session-h1', { consentReceiptId: 'receipt-h1', consentVersion: 'v1' }, 'consent-key'); await api.confirmResearchConsent('session-h1', { consentReceiptId: 'receipt-h1', consentVersion: 'v1' }, 'consent-key');
    await api.withdraw('session-h1', 'withdraw-key'); await api.withdraw('session-h1', 'withdraw-key');
    const mutationCalls = fetchMock.mock.calls.slice(1);
    for (const [, init] of mutationCalls) {
      const headers = new Headers((init as RequestInit).headers);
      expect((init as RequestInit).credentials).toBe('omit');
      expect(headers.get('Authorization')).toBe('Bearer bearer-h1');
    }
    expect(new Headers((mutationCalls[0][1] as RequestInit).headers).get('Idempotency-Key')).toBe(new Headers((mutationCalls[1][1] as RequestInit).headers).get('Idempotency-Key'));
    expect(new Headers((mutationCalls[2][1] as RequestInit).headers).get('Idempotency-Key')).toBe(new Headers((mutationCalls[3][1] as RequestInit).headers).get('Idempotency-Key'));
    expect(new Headers((mutationCalls[4][1] as RequestInit).headers).get('Idempotency-Key')).toBe(new Headers((mutationCalls[5][1] as RequestInit).headers).get('Idempotency-Key'));
    expect(new Headers((mutationCalls[6][1] as RequestInit).headers).get('Idempotency-Key')).toBe(new Headers((mutationCalls[7][1] as RequestInit).headers).get('Idempotency-Key'));
    expect(new Headers((mutationCalls[8][1] as RequestInit).headers).get('Idempotency-Key')).toBe(new Headers((mutationCalls[9][1] as RequestInit).headers).get('Idempotency-Key'));
  });
});
