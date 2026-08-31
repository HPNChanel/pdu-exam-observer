import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ApiError } from './api';
import type { ApiClient, EventStream, Health, ReviewerEvent, SessionSnapshot, StreamMessage } from './api';

class FakeApiClient implements ApiClient {
  state: SessionSnapshot['state'] = 'DRAFT'; failHealth = false; failAnswerOnce = false; answerKeys: string[] = []; starts = 0; stops = 0; reviewerSessionChecks = 0; reviewerActive = false;
  async health(): Promise<Health> { if (this.failHealth) throw new Error('offline'); return { schemaVersion: 1, status: 'ok' }; }
  async login(pin: string) { if (pin !== '2468') throw new ApiError(401); return { reviewer: 'Nghiên cứu viên' }; }
  async reviewerSession() { this.reviewerSessionChecks += 1; if (!this.reviewerActive) throw new ApiError(401); return { reviewer: 'Nghi\u00ean c\u1ee9u vi\u00ean' }; }
  async logout() {} async createSession() { return { id: 'S-20260824', pairingCode: 'MOC-248', snapshot: this.currentSnapshot() }; } async pair() { return { sessionId: 'S-20260824' }; }
  async consent() { this.state = 'CONSENT_CONFIRMED'; return this.currentSnapshot(); } async preflight() { this.state = 'PREFLIGHT_READY'; return this.currentSnapshot(); }
  async start() { this.starts += 1; this.state = 'RECORDING'; return this.currentSnapshot(); } async stop() { this.stops += 1; this.state = 'SEALED'; return this.currentSnapshot(); }
  async status() { return this.currentSnapshot(); } async answer(_answer: { answerId: string; questionId: string; value: string }, key: string) { this.answerKeys.push(key); if (this.failAnswerOnce) { this.failAnswerOnce = false; throw new Error('network'); } return { accepted: true }; }
  async submit() { return { submitted: true }; } async snapshot() { return this.currentSnapshot(); } async events() { return []; } async replay() {}
  currentSnapshot(): SessionSnapshot { return { sessionId: 'S-20260824', eventSeq: 1, state: this.state, submitted: false, durationSeconds: 2700, remainingSeconds: 2661, startedAtUtc: '2023-11-14T22:13:20Z' }; }
}

class FakeEventStream implements EventStream { private listener?: (message: StreamMessage) => void; private authLoss?: () => void; subscribe(onMessage: (message: StreamMessage) => void, _onStatus: (status: 'connected' | 'reconnecting') => void, onAuthLoss?: () => void) { this.listener = onMessage; this.authLoss = onAuthLoss; return () => undefined; } emit(event: ReviewerEvent) { this.listener?.({ kind: 'event', event }); } loseAuthorization() { this.authLoss?.(); } }
afterEach(() => vi.restoreAllMocks());

describe('health and demo boundaries', () => {
  it('blocks a failed live health check with retry and never silently switches to demo', async () => {
    const api = new FakeApiClient(); api.failHealth = true; render(<App route="/exam" api={api} />);
    expect(await screen.findByText(/Không thể kết nối hệ thống cục bộ/)).toBeInTheDocument(); expect(screen.queryByText(/DEMO NGOẠI TUYẾN/)).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Thử kết nối lại' })).toBeInTheDocument();
  });
});

describe('exam lifecycle', () => {
  it('requires consent and preflight, waits for reviewer RECORDING, then uses server timing and confirms submit', async () => {
    const api = new FakeApiClient(); render(<App route="/exam" api={api} />); await screen.findByText('Kết nối hệ thống cục bộ đã được xác nhận');
    fireEvent.change(screen.getByLabelText('Mã ghép cặp do người đánh giá cung cấp'), { target: { value: 'MOC-248' } }); fireEvent.click(screen.getByRole('button', { name: 'Ghép cặp phiên' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Xác nhận đồng ý' })); fireEvent.click(await screen.findByRole('button', { name: 'Hoàn tất kiểm tra trước thi' }));
    expect(await screen.findByText(/Đợi người đánh giá bắt đầu/)).toBeInTheDocument(); expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    api.state = 'RECORDING'; fireEvent.click(screen.getByRole('button', { name: 'Cập nhật trạng thái phiên' })); expect(await screen.findByText('44:21')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' })); expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });
  it('does not claim an answer is saved after failure and reuses its key only for retry', async () => {
    const api = new FakeApiClient(); api.failAnswerOnce = true; render(<App route="/exam" api={api} />); await screen.findByText('Kết nối hệ thống cục bộ đã được xác nhận');
    fireEvent.change(screen.getByLabelText('Mã ghép cặp do người đánh giá cung cấp'), { target: { value: 'MOC-248' } }); fireEvent.click(screen.getByRole('button', { name: 'Ghép cặp phiên' })); fireEvent.click(await screen.findByRole('button', { name: 'Xác nhận đồng ý' })); fireEvent.click(await screen.findByRole('button', { name: 'Hoàn tất kiểm tra trước thi' }));
    api.state = 'RECORDING'; fireEvent.click(await screen.findByRole('button', { name: 'Cập nhật trạng thái phiên' })); await screen.findByRole('radiogroup'); fireEvent.click(screen.getByLabelText('Chọn đáp án B')); expect(await screen.findByText(/Không thể lưu câu trả lời/)).toBeInTheDocument(); expect(screen.queryByText('Đã lưu')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lưu lại' })); await waitFor(() => expect(screen.getByText('Đã lưu')).toBeInTheDocument()); expect(api.answerKeys).toHaveLength(2); expect(api.answerKeys[0]).toBe(api.answerKeys[1]);
  });
});

describe('reviewer monitor', () => {
  it('validates a restored tab session on mount and returns to the PIN wall after stream auth loss', async () => {
    const api = new FakeApiClient(); api.reviewerActive = true; const events = new FakeEventStream(); render(<App route="/monitor" api={api} events={events} />);
    await waitFor(() => expect(api.reviewerSessionChecks).toBe(1)); expect(await screen.findByRole('button', { name: /T.o phi.n/ })).toBeInTheDocument();
    events.loseAuthorization();
    expect(await screen.findByRole('button', { name: /M. b.n quan s.t/ })).toBeInTheDocument();
  });
  it('reports invalid PIN, starts only from preflight-ready, receives events, stops, and logs out', async () => {
    const api = new FakeApiClient(); const events = new FakeEventStream(); render(<App route="/monitor" api={api} events={events} />); await waitFor(() => expect(screen.getByRole('button', { name: 'Mở bàn quan sát' })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('Mã PIN người đánh giá'), { target: { value: 'bad' } }); fireEvent.click(screen.getByRole('button', { name: 'Mở bàn quan sát' })); expect(await screen.findByText(/PIN không hợp lệ/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Mã PIN người đánh giá'), { target: { value: '2468' } }); fireEvent.click(screen.getByRole('button', { name: 'Mở bàn quan sát' })); fireEvent.click(await screen.findByRole('button', { name: 'Tạo phiên' })); await screen.findByText('MOC-248'); expect(screen.getByRole('button', { name: 'Bắt đầu ghi nhận' })).toBeDisabled();
    api.state = 'PREFLIGHT_READY'; fireEvent.click(screen.getByRole('button', { name: 'Cập nhật phiên' })); await waitFor(() => expect(screen.getByRole('button', { name: 'Bắt đầu ghi nhận' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Bắt đầu ghi nhận' })); await waitFor(() => expect(api.starts).toBe(1));
    events.emit({ id: 'event-2', eventSeq: 2, kind: 'technical', occurredAt: '#2', title: 'Dữ liệu kỹ thuật chưa đủ', confidence: null, confidenceStatus: 'INSUFFICIENT', durationSeconds: 0, signals: ['demo'] }); expect(await screen.findByText('Dữ liệu kỹ thuật chưa đủ')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dừng phiên' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Dừng phiên' })); await waitFor(() => expect(api.stops).toBe(1)); fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất' })); expect(await screen.findByRole('main', { name: 'Xác thực người đánh giá' })).toBeInTheDocument(); expect(screen.getByLabelText('Mã PIN người đánh giá')).toHaveValue('');
  });
});

