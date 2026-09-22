import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkspacePanel } from './WorkspacePanel';

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
});
