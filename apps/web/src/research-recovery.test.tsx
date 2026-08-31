import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ApiError } from './api';
import type { ApiClient, ResearchApi, ResearchReadiness, ResearchRecovery, ReviewerAuthLossSource, WithdrawalStatus } from './api';

const knownSessionId = 'research-oDUliIaM2hjS_xIg';
const readiness: ResearchReadiness = { ready: false, blockingGates: ['INSTITUTIONAL_APPROVAL_REQUIRED'] };
const draftRecovery: ResearchRecovery = { sessionId: knownSessionId, state: 'DRAFT', collectionBlocked: true, reauthenticationRequired: true };
const withdrawnRecovery: ResearchRecovery = { ...draftRecovery, state: 'WITHDRAWN' };
const withdrawn: WithdrawalStatus = { participantPseudonym: 'PDU-R-001', withdrawalReceiptId: 'withdrawal-r1', terminal: true, taskCount: 2 };

type RecoveryClient = ApiClient & ResearchApi & ReviewerAuthLossSource;

function createRecoveryClient(overrides: Partial<RecoveryClient> = {}): RecoveryClient {
  return {
    health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }),
    login: vi.fn(), reviewerSession: vi.fn(), logout: vi.fn(), createSession: vi.fn(), pair: vi.fn(), consent: vi.fn(), preflight: vi.fn(), start: vi.fn(), stop: vi.fn(), status: vi.fn(), answer: vi.fn(), submit: vi.fn(), snapshot: vi.fn(), events: vi.fn(), replay: vi.fn(),
    onReviewerAuthLoss: vi.fn(() => () => undefined), createStudy: vi.fn(), createParticipant: vi.fn(), createResearchSession: vi.fn(), confirmResearchConsent: vi.fn(),
    readiness: vi.fn().mockResolvedValue(readiness), getRecovery: vi.fn().mockResolvedValue(draftRecovery), withdraw: vi.fn(), withdrawalStatus: vi.fn().mockResolvedValue(withdrawn),
    ...overrides,
  } as RecoveryClient;
}

function remountAfterRestart(api: RecoveryClient) {
  const firstMount = render(<App route="/monitor" api={api} initialReviewer />);
  firstMount.unmount();
  return render(<App route="/monitor" api={api} initialReviewer />);
}

async function restoreKnownSession(): Promise<void> {
  fireEvent.change(screen.getByLabelText('Mã phiên nghiên cứu đã lưu'), { target: { value: knownSessionId } });
  fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên' }));
}

describe('M1 persisted research-session recovery', () => {
  beforeEach(() => { window.sessionStorage.clear(); window.history.replaceState({}, '', '/monitor'); });

  it('rehydrates a saved opaque session after a fresh remount without browser persistence', async () => {
    const api = createRecoveryClient();
    const initialHref = window.location.href;
    remountAfterRestart(api);

    expect(screen.getByLabelText('Mã phiên nghiên cứu đã lưu')).toHaveFocus();
    await restoreKnownSession();
    await screen.findByText(new RegExp(`Phiên nghiên cứu: ${knownSessionId}`));

    expect(api.getRecovery).toHaveBeenCalledWith(knownSessionId);
    expect(api.readiness).toHaveBeenCalledWith(knownSessionId);
    expect(screen.getByText(/Trạng thái khôi phục: Bản nháp/)).toBeInTheDocument();
    expect(screen.getByText('Chưa sẵn sàng cho thu thập')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Đã khôi phục phiên nghiên cứu');
    expect(document.activeElement).toBe(screen.getByRole('status'));
    expect(window.location.href).toBe(initialHref);
    expect(window.sessionStorage).toHaveLength(0);
  });

  it('loads withdrawal status and keeps restored terminal sessions mutation-locked', async () => {
    const api = createRecoveryClient({ getRecovery: vi.fn().mockResolvedValue(withdrawnRecovery) });
    remountAfterRestart(api);

    await restoreKnownSession();
    await screen.findByText('Đã rút khỏi nghiên cứu');

    expect(api.withdrawalStatus).toHaveBeenCalledWith(knownSessionId);
    expect(screen.getByText('Đã rút khỏi nghiên cứu')).toBeInTheDocument();
    expect(screen.getByLabelText('Mã biên nhận đồng ý')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Xác nhận đồng ý của người đánh giá' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' })).not.toBeInTheDocument();
  });

  it('rejects a non-opaque saved ID locally without calling recovery', async () => {
    const api = createRecoveryClient();
    remountAfterRestart(api);

    fireEvent.change(screen.getByLabelText('Mã phiên nghiên cứu đã lưu'), { target: { value: '../not-a-session' } });
    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Mã phiên nghiên cứu đã lưu không hợp lệ');
    expect(api.getRecovery).not.toHaveBeenCalled();
  });

  it('keeps a missing recovered resource scoped instead of declaring M1 unavailable', async () => {
    const api = createRecoveryClient({ getRecovery: vi.fn().mockRejectedValue(new ApiError(404, undefined, undefined, 'Not Found')) });
    remountAfterRestart(api);

    await restoreKnownSession();

    expect(await screen.findByRole('alert')).toHaveTextContent('tài nguyên recovery không còn tồn tại hoặc đã cũ');
    expect(screen.queryByText('Chế độ M1 chưa được bật')).not.toBeInTheDocument();
  });

  it('keeps the displayed recovery state when a later refresh rejects a mismatched session response', async () => {
    const getRecovery = vi.fn().mockResolvedValueOnce(draftRecovery).mockRejectedValueOnce(new Error('Research API response is invalid'));
    const api = createRecoveryClient({ getRecovery });
    remountAfterRestart(api);
    await restoreKnownSession();
    await screen.findByText(/Trạng thái khôi phục: Bản nháp/);

    fireEvent.click(screen.getByRole('button', { name: 'Tải trạng thái khôi phục' }));

    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent('Không thể tải trạng thái khôi phục');
    expect(screen.getByText(/Trạng thái khôi phục: Bản nháp/)).toBeInTheDocument();
  });

  it('returns to the PIN wall when recovery receives the existing reviewer-auth-loss callback', async () => {
    let onAuthLoss: (() => void) | undefined;
    const api = createRecoveryClient({
      onReviewerAuthLoss: vi.fn((listener: () => void) => { onAuthLoss = listener; return () => undefined; }),
      getRecovery: vi.fn().mockImplementation(async () => { onAuthLoss?.(); throw new ApiError(401); }),
    });
    remountAfterRestart(api);
    await waitFor(() => expect(api.onReviewerAuthLoss).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Mã phiên nghiên cứu đã lưu'), { target: { value: knownSessionId } });
    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên' }));

    expect(await screen.findByRole('heading', { name: 'Xác thực người đánh giá' })).toBeInTheDocument();
  });
});
