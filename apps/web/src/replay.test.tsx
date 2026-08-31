import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { ApiClient, EventStream, SessionSnapshot, StreamMessage } from './api';

const recordingSnapshot: SessionSnapshot = {
  sessionId: 'S-REPLAY', eventSeq: 3, state: 'RECORDING', submitted: false,
  durationSeconds: 2700, remainingSeconds: 2661, startedAtUtc: '2023-11-14T22:13:20Z',
};

class Stream implements EventStream {
  private listener?: (message: StreamMessage) => void;
  subscribe(onMessage: (message: StreamMessage) => void) { this.listener = onMessage; return () => undefined; }
  emit(message: StreamMessage) { this.listener?.(message); }
}

const monitorApi = (replay: ApiClient['replay'], snapshot = recordingSnapshot) => ({
  health: vi.fn().mockResolvedValue({ schemaVersion: 1, status: 'ok' }),
  createSession: vi.fn().mockResolvedValue({ id: snapshot.sessionId, pairingCode: 'PAIR-REPLAY', snapshot }),
  replay,
} as unknown as ApiClient);

describe('reviewer replay control', () => {
  it('requests replay once in RECORDING, reports pending/success truthfully, and waits for the stream to render cards', async () => {
    let resolveReplay: (() => void) | undefined;
    const replay = vi.fn(() => new Promise<void>((resolve) => { resolveReplay = resolve; }));
    const stream = new Stream();
    render(<App route="/monitor" api={monitorApi(replay)} events={stream} initialReviewer />);

    fireEvent.click(await screen.findByRole('button', { name: 'Tạo phiên' }));
    await screen.findByText('PAIR-REPLAY');
    fireEvent.click(screen.getByRole('button', { name: 'Phát lại dữ liệu mô phỏng' }));

    expect(replay).toHaveBeenCalledTimes(1);
    expect(replay).toHaveBeenCalledWith('S-REPLAY');
    expect(screen.getByRole('button', { name: 'Phát lại dữ liệu mô phỏng' })).toBeDisabled();
    expect(screen.getByText(/Đang yêu cầu phát dữ liệu mô phỏng/)).toBeInTheDocument();
    expect(screen.queryByRole('listitem', { name: /Sự kiện/i })).not.toBeInTheDocument();

    resolveReplay?.();
    await screen.findByText(/Yêu cầu phát dữ liệu mô phỏng đã được gửi/);
    stream.emit({ kind: 'event', event: { id: 'event-4', eventSeq: 4, kind: 'technical', occurredAt: '#4', title: 'Dữ liệu kỹ thuật chưa đủ', confidence: null, confidenceStatus: 'INSUFFICIENT', durationSeconds: 0, signals: ['synthetic_demo'] } });
    expect(await screen.findByText('Dữ liệu kỹ thuật chưa đủ')).toBeInTheDocument();
    expect(screen.getByText(/Thứ tự #4/)).toBeInTheDocument();
  });

  it('shows a truthful replay error and keeps replay disabled after a sealed session', async () => {
    const failedReplay = vi.fn().mockRejectedValue(new Error('offline'));
    const { rerender } = render(<App route="/monitor" api={monitorApi(failedReplay)} events={new Stream()} initialReviewer />);
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo phiên' }));
    await screen.findByText('PAIR-REPLAY');
    fireEvent.click(screen.getByRole('button', { name: 'Phát lại dữ liệu mô phỏng' }));
    expect(await screen.findByText(/Không thể yêu cầu phát dữ liệu mô phỏng/)).toBeInTheDocument();

    const sealed = { ...recordingSnapshot, state: 'SEALED' as const };
    rerender(<App route="/monitor" api={monitorApi(vi.fn().mockResolvedValue(undefined), sealed)} events={new Stream()} initialReviewer />);
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo phiên' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Phát lại dữ liệu mô phỏng' })).toBeDisabled());
    expect(screen.getByText(/không thể phát lại dữ liệu mô phỏng/)).toBeInTheDocument();
  });
});
