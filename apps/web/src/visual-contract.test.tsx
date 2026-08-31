import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { ApiClient, EventStream, SessionSnapshot, StreamMessage } from './api';

const snapshotFor = (state: SessionSnapshot['state']): SessionSnapshot => ({
  sessionId: `S-${state}`, eventSeq: 4, state, submitted: false,
  durationSeconds: 2700, remainingSeconds: state === 'RECORDING' ? 2661 : null,
  startedAtUtc: state === 'RECORDING' ? '2023-11-14T22:13:20Z' : null,
});

class Stream implements EventStream {
  private listener?: (message: StreamMessage) => void;
  subscribe(onMessage: (message: StreamMessage) => void) { this.listener = onMessage; return () => undefined; }
  emit(message: StreamMessage) { this.listener?.(message); }
}

const reviewerApi = (snapshot: SessionSnapshot) => ({
  health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }),
  createSession: vi.fn().mockResolvedValue({ id: snapshot.sessionId, pairingCode: 'PAIR-123', snapshot }),
} as unknown as ApiClient);

async function openMonitor(snapshot: SessionSnapshot, stream = new Stream()) {
  render(<App route="/monitor" api={reviewerApi(snapshot)} events={stream} initialReviewer />);
  fireEvent.click(await screen.findByRole('button', { name: 'Tạo phiên' }));
  return stream;
}

afterEach(() => vi.restoreAllMocks());

describe('monitor visual contract', () => {
  it('makes the recording phase dominant while demoting a consumed pairing code', async () => {
    await openMonitor(snapshotFor('RECORDING'));
    expect(await screen.findByRole('heading', { name: 'Đang ghi nhận' })).toBeInTheDocument();
    expect(screen.getByText('PAIR-123').closest('.pairingCode')).toHaveClass('pairingCode--demoted');
  });

  it('makes a sealed session unambiguous without rendering its pairing code', async () => {
    await openMonitor(snapshotFor('SEALED'));
    expect(await screen.findByRole('heading', { name: 'Phiên đã niêm phong' })).toBeInTheDocument();
    expect(screen.queryByText('PAIR-123')).not.toBeInTheDocument();
    expect(screen.getByText(/không thể phát lại dữ liệu mô phỏng/)).toBeInTheDocument();
  });

  it('shows a single authoritative sequence label for streamed evidence', async () => {
    const stream = await openMonitor(snapshotFor('RECORDING'));
    stream.emit({ kind: 'event', event: { id: 'event-4', eventSeq: 4, kind: 'technical', occurredAt: '#4', title: 'Dữ liệu kỹ thuật chưa đủ', confidence: null, confidenceStatus: 'INSUFFICIENT', durationSeconds: 0, signals: ['synthetic_demo'] } });
    expect(await screen.findByText('Thứ tự #4')).toBeInTheDocument();
    expect(screen.queryByText('Thứ tự #4 · #4')).not.toBeInTheDocument();
  });

  it('resets monitor auth loss to top and focuses the PIN input without ordinary state updates', async () => {
    const scrollTo = vi.fn();
    vi.stubGlobal('scrollTo', scrollTo);
    const api = { health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }), reviewerSession: vi.fn().mockRejectedValue(new Error('unauthorized')) } as unknown as ApiClient;
    render(<App route="/monitor" api={api} events={new Stream()} />);
    const pin = await screen.findByLabelText('Mã PIN người đánh giá');
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' }));
    expect(pin).toHaveFocus();
  });

  it('marks Vietnamese display text as NFC-safe rather than applying tracked headline glyphs', async () => {
    const examApi = { health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }), pair: vi.fn().mockResolvedValue({ sessionId: 'S-EXAM' }), status: vi.fn().mockResolvedValue(snapshotFor('RECORDING')) } as unknown as ApiClient;
    render(<App route="/exam" api={examApi} />);
    await screen.findByText('Kết nối hệ thống cục bộ đã được xác nhận');
    fireEvent.change(screen.getByLabelText('Mã ghép cặp do người đánh giá cung cấp'), { target: { value: 'PAIR-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ghép cặp phiên' }));
    const prompt = await screen.findByRole('heading', { name: /Một ngăn xếp/ });
    expect(prompt).toHaveClass('nfcText');
    expect(prompt.textContent).toBe(prompt.textContent?.normalize('NFC'));
  });
});
