import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ApiError, HttpApiClient } from './api';
import type { ApiClient, ResearchReadiness, ResearchRecovery, ResearchSession, ResearchStudy, ResearchParticipant, WithdrawalStatus } from './api';

type ResearchClient = ApiClient & {
  createStudy(studyCode: string, idempotencyKey: string): Promise<ResearchStudy>;
  createParticipant(studyId: string, idempotencyKey: string): Promise<ResearchParticipant>;
  createResearchSession(input: { studyId: string; participantId: string; retentionPolicyReference?: string; retentionEndDate?: string }, idempotencyKey: string): Promise<ResearchSession>;
  confirmResearchConsent(sessionId: string, input: { consentReceiptId: string; consentVersion: string }, idempotencyKey: string): Promise<ResearchSession>;
  readiness(sessionId: string): Promise<ResearchReadiness>;
  getRecovery(sessionId: string): Promise<ResearchRecovery>;
  withdraw(sessionId: string, idempotencyKey: string): Promise<WithdrawalStatus>;
};

const session: ResearchSession = { id: 'session-r1', studyId: 'study-r1', participantId: 'participant-r1', participantPseudonym: 'PDU-R-001', state: 'DRAFT' };
const blockedReadiness: ResearchReadiness = {
  ready: false,
  blockingGates: ['OPERATOR_CONSENT_REQUIRED', 'INSTITUTIONAL_APPROVAL_REQUIRED', 'UNMAPPED_GATE'],
};
const recovery: ResearchRecovery = { sessionId: session.id, state: 'DRAFT', collectionBlocked: true, reauthenticationRequired: true };
const withdrawal: WithdrawalStatus = { participantPseudonym: 'PDU-R-001', withdrawalReceiptId: 'withdrawal-r1', terminal: true, taskCount: 2 };

function createResearchClient(overrides: Partial<ResearchClient> = {}): ResearchClient {
  const base = {
    health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }),
    login: vi.fn().mockResolvedValue({ reviewer: 'Nghiên cứu viên' }), reviewerSession: vi.fn().mockResolvedValue({ reviewer: 'Nghiên cứu viên' }), logout: vi.fn().mockResolvedValue(undefined),
    createSession: vi.fn(), pair: vi.fn(), consent: vi.fn(), preflight: vi.fn(), start: vi.fn(), stop: vi.fn(), status: vi.fn(), answer: vi.fn(), submit: vi.fn(), snapshot: vi.fn(), events: vi.fn(), replay: vi.fn(),
  } as ApiClient;
  return {
    ...base,
    createStudy: vi.fn().mockResolvedValue({ id: 'study-r1', studyCode: 'PDU-M1-01' }),
    createParticipant: vi.fn().mockResolvedValue({ id: 'participant-r1', pseudonym: 'PDU-R-001' }),
    createResearchSession: vi.fn().mockResolvedValue(session),
    confirmResearchConsent: vi.fn().mockResolvedValue({ ...session, state: 'CONSENT_CONFIRMED' }),
    readiness: vi.fn().mockResolvedValue(blockedReadiness),
    getRecovery: vi.fn().mockResolvedValue(recovery),
    withdraw: vi.fn().mockResolvedValue(withdrawal),
    ...overrides,
  };
}

async function createDraftFlow(api: ResearchClient): Promise<void> {
  render(<App route="/monitor" api={api} initialReviewer />);
  fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-M1-01' } });
  fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
  await screen.findByText('PDU-M1-01');
  fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
  await screen.findByText('PDU-R-001');
}

describe('M1 research preparation', () => {
  beforeEach(() => { window.sessionStorage.clear(); });

  it('is absent before reviewer authorization and becomes a separate workflow after authorization', () => {
    const api = createResearchClient();
    const { unmount } = render(<App route="/monitor" api={api} initialReviewer={false} />);
    expect(screen.queryByRole('region', { name: 'Chuẩn bị nghiên cứu' })).not.toBeInTheDocument();
    unmount();
    render(<App route="/monitor" api={api} initialReviewer />);
    expect(screen.getByRole('region', { name: 'Chuẩn bị nghiên cứu' })).toBeInTheDocument();
    expect(screen.getByText('Chưa có phê duyệt thể chế; M1 không thể ghi nhận hoặc thu thập dữ liệu.')).toBeInTheDocument();
  });

  it('shows the truthful M1 unavailable state when the M0 backend returns 404', async () => {
    const api = createResearchClient({ createStudy: vi.fn().mockRejectedValue(new ApiError(404, undefined, undefined, 'Not Found')) });
    render(<App route="/monitor" api={api} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-M1-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    expect(await screen.findByText('Chế độ M1 chưa được bật')).toBeInTheDocument();
    expect(screen.queryByText('DEMO NGOẠI TUYẾN')).not.toBeInTheDocument();
  });

  it('creates a draft, pseudonymous participant, and session with a stable idempotency key for retry', async () => {
    const createSession = vi.fn().mockRejectedValueOnce(new ApiError(503)).mockResolvedValue(session);
    const api = createResearchClient({ createResearchSession: createSession });
    await createDraftFlow(api);
    fireEvent.click(screen.getByLabelText('Tham chiếu chính sách lưu giữ'));
    fireEvent.change(screen.getByLabelText('Tham chiếu chính sách lưu giữ'), { target: { value: 'retention-2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể khởi tạo phiên nghiên cứu');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-r1');
    expect(createSession).toHaveBeenCalledTimes(2);
    expect(createSession.mock.calls[0][0]).toEqual({ studyId: 'study-r1', participantId: 'participant-r1', retentionPolicyReference: 'retention-2026' });
    expect(createSession.mock.calls[1][1]).toBe(createSession.mock.calls[0][1]);
  });

  it('permits only one optional retention decision in the session request', async () => {
    const api = createResearchClient();
    await createDraftFlow(api);
    fireEvent.click(screen.getByLabelText('Ngày kết thúc lưu giữ'));
    fireEvent.change(screen.getByLabelText('Ngày kết thúc lưu giữ'), { target: { value: '31/12/2027' } });
    expect(screen.getByLabelText('Ngày kết thúc lưu giữ')).toHaveAttribute('type', 'text');
    expect(screen.getByText('Nhập theo định dạng dd/mm/yyyy.')).toBeInTheDocument();
    expect(screen.getByLabelText('Tham chiếu chính sách lưu giữ')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    await waitFor(() => expect(api.createResearchSession).toHaveBeenCalled());
    expect(api.createResearchSession).toHaveBeenCalledWith({ studyId: 'study-r1', participantId: 'participant-r1', retentionEndDate: '2027-12-31' }, expect.any(String));
    expect(await screen.findByText('Ngày kết thúc lưu giữ đã ghi: 31/12/2027')).toBeInTheDocument();
  });

  it('blocks malformed, impossible, and past text retention dates before a session request', async () => {
    for (const value of ['2027-12-31', '31/02/2027', '24/08/2026']) {
      const api = createResearchClient();
      const view = render(<App route="/monitor" api={api} initialReviewer />);
      fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-M1-01' } });
      fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
      await screen.findByText('PDU-M1-01');
      fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
      await screen.findByText('PDU-R-001');
      fireEvent.change(screen.getByLabelText('Ngày kết thúc lưu giữ'), { target: { value } });
      fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
      expect(await screen.findByRole('alert')).toBeInTheDocument();
      expect(api.createResearchSession).not.toHaveBeenCalled();
      view.unmount();
    }
  });

  it('keeps reviewer consent confirmation separate from the candidate flow and renders typed blocked gates', async () => {
    const api = createResearchClient();
    await createDraftFlow(api);
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-r1');
    fireEvent.change(screen.getByLabelText('Mã biên nhận đồng ý'), { target: { value: 'receipt-r1' } });
    fireEvent.change(screen.getByLabelText('Phiên bản đồng ý'), { target: { value: 'v1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận đồng ý của người đánh giá' }));
    await waitFor(() => expect(api.confirmResearchConsent).toHaveBeenCalledWith('session-r1', { consentReceiptId: 'receipt-r1', consentVersion: 'v1' }, expect.any(String)));
    fireEvent.click(screen.getByRole('button', { name: 'Tải cổng sẵn sàng' }));
    expect(await screen.findByText('Chưa sẵn sàng cho thu thập')).toBeInTheDocument();
    expect(screen.getByText('Cần xác nhận đồng ý')).toBeInTheDocument();
    expect(screen.getByText('Cần phê duyệt thể chế')).toBeInTheDocument();
    expect(screen.getByText('Mã kỹ thuật chưa hỗ trợ: UNMAPPED_GATE')).toBeInTheDocument();
  });

  it('makes withdrawal terminal and shows reconciliation and recovery state', async () => {
    const api = createResearchClient();
    await createDraftFlow(api);
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-r1');
    fireEvent.click(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận rút khỏi nghiên cứu' }));
    expect(await screen.findByText('Đã rút khỏi nghiên cứu')).toBeInTheDocument();
    expect(screen.getByText('2 tác vụ đối soát đang chờ')).toBeInTheDocument();
    expect(screen.getByText('Thu thập bị chặn; cần xác thực lại khi khôi phục.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Xác nhận đồng ý của người đánh giá' })).toBeDisabled();
  });

  it('localizes lifecycle states and puts irreversible withdrawal consequences beside the trigger', async () => {
    const api = createResearchClient();
    await createDraftFlow(api);
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-r1');
    fireEvent.click(screen.getByRole('button', { name: 'Tải trạng thái khôi phục' }));
    expect(await screen.findByText('Trạng thái khôi phục: Bản nháp')).toBeInTheDocument();
    expect(screen.queryByText('Trạng thái khôi phục: DRAFT')).not.toBeInTheDocument();
    const trigger = screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' });
    expect(trigger.closest('.withdrawalPanel')).toHaveTextContent('Rút khỏi nghiên cứu áp dụng cho người tham gia này và tất cả phiên nghiên cứu liên quan của họ. Xuất và hiện vật phải được đối soát; không thể hoàn tác trong M1.');
    fireEvent.click(trigger);
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('Thao tác này áp dụng cho người tham gia này và tất cả phiên nghiên cứu liên quan của họ. Xuất và hiện vật phải được đối soát; không thể hoàn tác trong M1.');
    expect(screen.queryByText(/terminal/i)).not.toBeInTheDocument();
  });
});

describe('M1 API boundary', () => {
  it('uses reviewer bearer, omit credentials, and clears it after a 401 without putting it in a URL', async () => {
    window.sessionStorage.setItem('pdu-exam-observer.reviewer-session.v1', JSON.stringify({ schemaVersion: 1, accessToken: 'reviewer-secret', expiresAtUtc: '2026-08-25T00:00:00Z', reviewer: 'R' }));
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code: 'REVOKED' } }), { status: 401, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new HttpApiClient('monitor') as unknown as ResearchClient;
    expect(typeof api.createStudy).toBe('function');
    await expect(api.createStudy('PDU-M1-01', 'study-key')).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/research/studies', expect.objectContaining({ credentials: 'omit', headers: expect.objectContaining({ Authorization: 'Bearer reviewer-secret', 'Idempotency-Key': 'study-key' }) }));
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('reviewer-secret');
    expect(window.sessionStorage.getItem('pdu-exam-observer.reviewer-session.v1')).toBeNull();
  });
});
