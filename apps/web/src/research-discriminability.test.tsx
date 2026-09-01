import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { HttpApiClient } from './api';

const tokenKey = 'pdu-exam-observer.reviewer-session.v1';
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const authenticatedClient = () => {
  window.sessionStorage.clear();
  window.sessionStorage.setItem(tokenKey, JSON.stringify({ schemaVersion: 1, accessToken: 'reviewer-discriminability-token', expiresAtUtc: '2026-08-27T00:00:00Z', reviewer: 'R' }));
  return new HttpApiClient('monitor');
};
const health = { schema_version: 1, status: 'ok' };
const study = { schema_version: 1, study_id: 'study-d1', status: 'APPROVAL_PENDING' };
const participant = { schema_version: 1, participant_id: 'participant-d1', participant_pseudonym: 'PDU-D-001' };
const session = { schema_version: 1, session_id: 'session-d1', session_kind: 'RESEARCH', participant_pseudonym: 'PDU-D-001', state: 'DRAFT' };
const consented = { schema_version: 1, session_id: 'session-d1', consent_confirmed: true };
const recovery = { schema_version: 1, session_id: 'session-d1', state: 'DRAFT', collection_blocked: true, reauthentication_required: true };
const withdrawal = { schema_version: 1, withdrawal_receipt_id: 'withdraw-d1', participant_pseudonym: 'PDU-D-001', terminal: true, task_count: 1 };

afterEach(() => { vi.unstubAllGlobals(); window.sessionStorage.clear(); });

async function createThroughSession(): Promise<void> {
  fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-D-01' } });
  fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
  await screen.findByText('PDU-D-01');
  fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
  await screen.findByText('PDU-D-001');
  fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
  await screen.findByText('Phiên nghiên cứu: session-d1');
}

describe('M1 discriminability through the production HTTP client', () => {
  it('delivers an ordinary research 401 to the auth-loss callback and Monitor PIN wall', async () => {
    const api = authenticatedClient();
    const callback = vi.fn();
    api.onReviewerAuthLoss(callback);
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => url.endsWith('/health') ? Promise.resolve(json(health)) : Promise.resolve(json({ detail: 'expired' }, 401))));
    render(<App route="/monitor" api={api} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-D-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    await waitFor(() => expect(callback).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('button', { name: 'Mở bàn quan sát' })).toBeInTheDocument();
    expect(window.sessionStorage.getItem(tokenKey)).toBeNull();
  });

  it('only treats the exact absent-route 404 as M1-disabled', async () => {
    const routeApi = authenticatedClient();
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => url.endsWith('/health') ? Promise.resolve(json(health)) : Promise.resolve(json({ detail: 'Not Found' }, 404))));
    const { unmount } = render(<App route="/monitor" api={routeApi} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-D-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    expect(await screen.findByText('Chế độ M1 chưa được bật')).toBeInTheDocument();
    unmount();
    const resourceApi = authenticatedClient();
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => url.endsWith('/health') ? Promise.resolve(json(health)) : Promise.resolve(json({ detail: 'Research study not found' }, 404))));
    render(<App route="/monitor" api={resourceApi} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-D-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    const scoped = await within(screen.getByRole('region', { name: 'Chuẩn bị nghiên cứu' })).findByRole('alert');
    expect(scoped).toHaveTextContent('bản nháp nghiên cứu không còn tồn tại hoặc đã cũ');
    expect(screen.getByRole('region', { name: 'Chuẩn bị nghiên cứu' })).toBeInTheDocument();
  });

  it('retries every M1 mutation with the same nonempty key and exact monitor auth boundary', async () => {
    const attempts = new Map<string, number>();
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/health')) return Promise.resolve(json(health));
      if (url.endsWith('/recovery')) return Promise.resolve(json(recovery));
      const count = (attempts.get(url) ?? 0) + 1; attempts.set(url, count);
      if (count === 1) return Promise.resolve(json({ detail: { code: 'IDEMPOTENCY_CONFLICT', message: 'conflict' } }, 409));
      if (url.endsWith('/studies')) return Promise.resolve(json(study, 201));
      if (url.endsWith('/participants')) return Promise.resolve(json(participant, 201));
      if (url.endsWith('/research/sessions')) return Promise.resolve(json(session, 201));
      if (url.endsWith('/consent-confirmation')) return Promise.resolve(json(consented));
      if (url.endsWith('/withdrawal')) return Promise.resolve(json(withdrawal));
      throw new Error(`Unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App route="/monitor" api={authenticatedClient()} initialReviewer />);
    fireEvent.change(screen.getByLabelText('Mã nghiên cứu'), { target: { value: 'PDU-D-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo bản nháp nghiên cứu' }));
    const studyConflict = await within(screen.getByRole('region', { name: 'Chuẩn bị nghiên cứu' })).findByRole('alert');
    expect(studyConflict).toHaveTextContent('xung đột');
    expect(studyConflict.closest('section')).toHaveTextContent('1. Bản nháp nghiên cứu');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại tạo bản nháp nghiên cứu' }));
    await screen.findByText('PDU-D-01');
    fireEvent.click(screen.getByRole('button', { name: 'Tạo mã giả danh người tham gia' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại tạo mã giả danh' }));
    await screen.findByText('PDU-D-001');
    fireEvent.change(screen.getByLabelText('Tham chiếu chính sách lưu giữ'), { target: { value: 'retention-d1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Khởi tạo phiên nghiên cứu' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại khởi tạo phiên nghiên cứu' }));
    await screen.findByText('Phiên nghiên cứu: session-d1');
    fireEvent.change(screen.getByLabelText('Mã biên nhận đồng ý'), { target: { value: 'receipt-d1' } });
    fireEvent.change(screen.getByLabelText('Phiên bản đồng ý'), { target: { value: 'v1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận đồng ý của người đánh giá' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại xác nhận đồng ý' }));
    fireEvent.click(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận rút khỏi nghiên cứu' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại rút khỏi nghiên cứu' }));
    await screen.findByText('Đã rút khỏi nghiên cứu');
    const paths = ['/research/studies', '/research/participants', '/research/sessions', '/consent-confirmation', '/withdrawal'];
    for (const path of paths) {
      const calls = fetchMock.mock.calls.filter((call) => String(call[0]).endsWith(path));
      expect(calls).toHaveLength(2);
      const first = calls[0][1] as RequestInit; const second = calls[1][1] as RequestInit;
      const headers = new Headers(first.headers); const retryHeaders = new Headers(second.headers);
      expect(headers.get('Idempotency-Key')).toBeTruthy();
      expect(retryHeaders.get('Idempotency-Key')).toBe(headers.get('Idempotency-Key'));
      expect(headers.get('Authorization')).toBe('Bearer reviewer-discriminability-token');
      expect(retryHeaders.get('Authorization')).toBe('Bearer reviewer-discriminability-token');
      expect(first.credentials).toBe('omit'); expect(second.credentials).toBe('omit');
    }
  });

  it('fails closed for missing and wrong schema versions in every M1 mapper', async () => {
    const invalid = [
      { study_id: 's', study_code: 'c' }, { schema_version: 2, participant_id: 'p', participant_pseudonym: 'P' }, { session_id: 'x', study_id: 's', participant_id: 'p', participant_pseudonym: 'P', state: 'DRAFT' }, { ...consented, schema_version: 2 }, { ready: false, blocking_gates: [] }, { ...recovery, schema_version: 2 }, { participant_pseudonym: 'P', withdrawal_receipt_id: null, terminal: false, task_count: 0 },
    ];
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(json(invalid.shift()))));
    const api = authenticatedClient();
    await expect(api.createStudy('c', 'a')).rejects.toThrow('Research API response is invalid');
    await expect(api.createParticipant('s', 'b')).rejects.toThrow('Research API response is invalid');
    await expect(api.createResearchSession({ studyId: 's', participantId: 'p' }, 'c')).rejects.toThrow('Research API response is invalid');
    await expect(api.confirmResearchConsent('x', { consentReceiptId: 'r', consentVersion: 'v' }, 'd')).rejects.toThrow('Research API response is invalid');
    await expect(api.readiness('x')).rejects.toThrow('Research API response is invalid');
    await expect(api.getRecovery('x')).rejects.toThrow('Research API response is invalid');
    await expect(api.withdraw('x', 'e')).rejects.toThrow('Research API response is invalid');
  });

  it('contains withdrawal focus on Tab and Shift+Tab, cancels on Escape, and restores the trigger', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/health')) return Promise.resolve(json(health));
      if (url.endsWith('/studies')) return Promise.resolve(json(study, 201));
      if (url.endsWith('/participants')) return Promise.resolve(json(participant, 201));
      if (url.endsWith('/research/sessions')) return Promise.resolve(json(session, 201));
      if (url.endsWith('/recovery')) return Promise.resolve(json(recovery));
      throw new Error(`Unexpected ${url}`);
    }));
    render(<App route="/monitor" api={authenticatedClient()} initialReviewer />);
    await createThroughSession();
    fireEvent.click(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' }));
    const dialog = await screen.findByRole('alertdialog');
    const cancel = screen.getByRole('button', { name: 'Quay lại' }); const confirm = screen.getByRole('button', { name: 'Xác nhận rút khỏi nghiên cứu' });
    await waitFor(() => expect(document.activeElement).toBe(cancel));
    fireEvent.keyDown(dialog, { key: 'Tab' }); expect(document.activeElement).toBe(confirm);
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true }); expect(document.activeElement).toBe(cancel);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Yêu cầu rút khỏi nghiên cứu' })));
  });
});
