import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkspacePanel } from './WorkspacePanel';

type Session = Record<string, unknown>;

const makeApi = (session: Session) => ({
  workspaceRequest: vi.fn(async (path: string) =>
    path === ''
      ? { sessions: [session], model: { status: 'MODEL_UNAVAILABLE' } }
      : { ...session, events: [{ event_id: 'e1', label: 'NORMAL', start_ms: 0, end_ms: 6000, review_status: 'UNREVIEWED', revision: 0 }] }),
  workspaceDownload: vi.fn(), workspaceImport: vi.fn(),
});

const openSession = async () => {
  fireEvent.click(screen.getByRole('button', { name: /Mở phiên/ }));
  await screen.findByRole('heading', { name: 'Duyệt sự kiện' });
};

describe('research workspace', () => {
  it('shows provenance and requires review before export', async () => {
    const session = { session_id: 's1', source_kind: 'AI_RENDERED', state: 'SEALED', revision: 1, locked: false, event_count: 1 };
    const api = {
      workspaceRequest: vi.fn(async (path: string) => path === '' ? { sessions: [session], model: { status: 'MODEL_UNAVAILABLE' } } : { ...session, events: [{ event_id: 'e1', label: 'NORMAL', start_ms: 0, end_ms: 6000, review_status: 'UNREVIEWED', revision: 0 }] }),
      workspaceDownload: vi.fn(), workspaceImport: vi.fn(),
    };
    render(<WorkspacePanel api={api} onLogout={() => undefined} />);
    await screen.findByText('Dữ liệu mô phỏng');
    fireEvent.click(screen.getByRole('button', { name: /Mở phiên/ }));
    await screen.findByRole('heading', { name: 'Duyệt sự kiện' });
    expect(screen.getByRole('button', { name: 'Xuất dữ liệu pose' })).toBeDisabled();
    expect(screen.getByText(/chưa có mô hình/i)).toBeInTheDocument();
    await waitFor(() => expect(api.workspaceRequest).toHaveBeenCalledWith('/sessions/s1'));
  });

  it('renders drop and gap metrics from the session record', async () => {
    const session = { session_id: 's1', source_kind: 'AI_RENDERED', state: 'RECORDING', dropped_frames: 12, gap_events: 3, max_gap_frames: 8 };
    render(<WorkspacePanel api={makeApi(session)} onLogout={() => undefined} />);
    await screen.findByText('Dữ liệu mô phỏng');
    await openSession();
    expect(screen.getByText('Khung mất').nextSibling).toHaveTextContent('12');
    expect(screen.getByText('Đứt đoạn').nextSibling).toHaveTextContent('3 / 8 khung');
  });

  it('gates mark-contamination to RECORDING sessions only', async () => {
    for (const state of ['DRAFT', 'STOPPED', 'SEALED']) {
      const { unmount } = render(<WorkspacePanel api={makeApi({ session_id: 's1', source_kind: 'AI_RENDERED', state })} onLogout={() => undefined} />);
      await screen.findByText('Dữ liệu mô phỏng');
      await openSession();
      expect(screen.getByRole('button', { name: 'Đánh dấu nhiễm thao tác' })).toBeDisabled();
      unmount();
    }
    render(<WorkspacePanel api={makeApi({ session_id: 's1', source_kind: 'AI_RENDERED', state: 'RECORDING', contaminated_by_operator: true })} onLogout={() => undefined} />);
    await screen.findByText('Dữ liệu mô phỏng');
    await openSession();
    expect(screen.getByRole('button', { name: 'Đánh dấu nhiễm thao tác' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Đã đánh dấu nhiễm thao tác');
  });

  it('posts mark-contamination with an idempotency key and refetches', async () => {
    const api = makeApi({ session_id: 's1', source_kind: 'AI_RENDERED', state: 'RECORDING' });
    render(<WorkspacePanel api={api} onLogout={() => undefined} />);
    await screen.findByText('Dữ liệu mô phỏng');
    await openSession();
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu nhiễm thao tác' }));
    await waitFor(() => expect(api.workspaceRequest).toHaveBeenCalledWith(
      '/sessions/s1/mark-contamination',
      expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'Idempotency-Key': expect.any(String) }) }),
    ));
    await waitFor(() => expect(api.workspaceRequest.mock.calls.filter(([p]) => p === '/sessions/s1').length).toBeGreaterThanOrEqual(2));
  });
});
