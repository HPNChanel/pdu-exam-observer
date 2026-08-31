import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError, type ReconciliationPlan, type ResearchApi } from './api';
import { ReconciliationPanel } from './ReconciliationPanel';

const plan: ReconciliationPlan = {
  participantPseudonym: 'PDU-R-001',
  planSha256: 'a'.repeat(64),
  confirmationPhrase: 'DOI_SOAT PDU-R-001 abcdef123456',
  localTargetTotal: 1,
  externalTargetTotal: 1,
  blockedTargetTotal: 0,
  recoveryRequiredTotal: 0,
  complete: false,
  blockerCodes: [],
  targets: [],
};

function api(): ResearchApi {
  return {
    reconciliation: vi.fn().mockResolvedValue(plan),
    createReconciliationChallenge: vi.fn().mockResolvedValue({
      challengeId: 'challenge-1',
      challengeToken: 'secret-token',
      planSha256: plan.planSha256,
      confirmationPhrase: plan.confirmationPhrase,
      expiresAt: 1_800_000_120,
    }),
    executeReconciliation: vi
      .fn()
      .mockRejectedValue(new ApiError(403, undefined, 'AUTHORITY_NOT_ISSUED')),
  } as unknown as ResearchApi;
}

describe('M1-R1 reconciliation panel', () => {
  it('separates counts, requires exact step-up confirmation, and renders authority denial', async () => {
    const client = api();
    render(<ReconciliationPanel api={client} sessionId="session-r1" />);

    expect(await screen.findByText('Người tham gia: PDU-R-001')).toBeInTheDocument();
    expect(screen.getByText('Bản sao bên ngoài')).toBeInTheDocument();
    expect(screen.getByText(/không kết nối tài khoản bên ngoài/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Nhập lại PIN người đánh giá'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo xác nhận xóa cục bộ' }));
    expect(await screen.findByText(plan.confirmationPhrase)).toBeInTheDocument();

    const execute = screen.getByRole('button', { name: 'Thực thi đối soát cục bộ' });
    expect(execute).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Cụm xác nhận'), {
      target: { value: plan.confirmationPhrase },
    });
    expect(execute).toBeEnabled();
    fireEvent.click(execute);

    expect(
      await screen.findByText('Chưa có thẩm quyền thực thi xóa dữ liệu thật.'),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(client.executeReconciliation).toHaveBeenCalledWith(
        'session-r1',
        'secret-token',
        plan.confirmationPhrase,
      ),
    );
    expect(screen.queryByText(plan.confirmationPhrase)).not.toBeInTheDocument();
  });
});
