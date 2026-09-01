import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError, type SyntheticReviewApi, type SyntheticReviewRun } from './api';
import { SyntheticValidationPanel } from './SyntheticValidationPanel';

const queued: SyntheticReviewRun = {
  schemaVersion: 1,
  requestId: 'synrun-0123456789abcdef0123456789abcdef',
  runSequence: 1,
  runKind: 'PREFLIGHT_60S',
  jobStatus: 'QUEUED',
  serviceFailureCode: null,
  receipt: null,
};

const digest = 'a'.repeat(64);

function terminal(outcome: 'BACKEND_CONTRACT_PASS' | 'NO_GO' = 'BACKEND_CONTRACT_PASS', persisted = true): SyntheticReviewRun {
  return {
    ...queued,
    jobStatus: 'TERMINAL',
    receipt: {
      schemaVersion: 1,
      status: persisted ? 'M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY' : 'M2_S2A_SYNTHETIC_PREFLIGHT_NOT_PERSISTED',
      integrationStatus: persisted ? 'PERSISTED' : 'NOT_PERSISTED',
      evidenceKind: 'SIMULATED',
      runKind: 'PREFLIGHT_60S',
      d1Outcome: persisted ? outcome : null,
      d1FailureCode: outcome === 'NO_GO' ? 'QUALITY_INSUFFICIENT' : null,
      integrationFailureCode: persisted ? null : 'PERSISTENCE_FAILED',
      deviceGateDecision: 'UNVERIFIED',
      d1Go: false,
      authorityStatus: 'AUTHORITY_NOT_ISSUED',
      physicalCameraAccessAuthorized: false,
      participantCollectionAuthorized: false,
      collectionAuthorized: false,
      observationCount: persisted ? 977 : 0,
      observationDigest: persisted ? digest : null,
      d1ReceiptDigest: persisted ? digest : null,
      artifactId: persisted ? 'artifact-synthetic-001' : null,
      artifactSha256: persisted ? digest : null,
      manifestSchemaVersion: persisted ? 2 : null,
      packageContainsIntegration: false,
      resultDigest: digest,
    },
  };
}

function api(overrides: Partial<SyntheticReviewApi> = {}): SyntheticReviewApi {
  return {
    listSyntheticRuns: vi.fn().mockResolvedValue([]),
    createSyntheticRun: vi.fn().mockResolvedValue(terminal()),
    getSyntheticRun: vi.fn().mockResolvedValue(terminal()),
    downloadSyntheticEvidence: vi.fn().mockResolvedValue({
      bytes: new TextEncoder().encode('{"artifact_kind":"M2_SYNTHETIC_EVIDENCE_BUNDLE"}\n'),
      filename: `${queued.requestId}.json`,
      sha256: digest,
    }),
    ...overrides,
  };
}

describe('synthetic validation panel', () => {
  it('hides completely only when the optional route is exactly missing', async () => {
    render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockRejectedValue(new ApiError(404, undefined, undefined, 'Not Found')) })} />);
    await waitFor(() => expect(screen.queryByText(/MÔ PHỎNG/)).not.toBeInTheDocument());
    const unavailable = render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockRejectedValue(new ApiError(503, undefined, 'SERVICE_CLOSED')) })} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Tính năng xác minh synthetic tạm thời không khả dụng.');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    unavailable.unmount();
  });

  it('shows the non-authorizing banner and exactly two fixed run buttons', async () => {
    render(<SyntheticValidationPanel api={api()} />);
    expect(await screen.findByText('MÔ PHỎNG — KHÔNG CAMERA — KHÔNG CẤP QUYỀN THU DỮ LIỆU')).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Chạy nominal mô phỏng 20 phút (18.077 frame tăng tốc)' })).toBeInTheDocument();
  });

  it('posts once with one key and polls only by GET until terminal', async () => {
    const client = api({
      createSyntheticRun: vi.fn().mockResolvedValue(queued),
      getSyntheticRun: vi.fn().mockResolvedValue(terminal()),
    });
    render(<SyntheticValidationPanel api={client} pollIntervalMs={1} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    await screen.findByText('Contract synthetic đạt; thiết bị vẫn chưa được xác minh.');
    expect(client.createSyntheticRun).toHaveBeenCalledTimes(1);
    expect(client.getSyntheticRun).toHaveBeenCalledWith(queued.requestId);
  });

  it('disables both actions while one run is active', async () => {
    const client = api({ createSyntheticRun: vi.fn().mockResolvedValue(queued), getSyntheticRun: vi.fn(() => new Promise<SyntheticReviewRun>(() => undefined)) });
    render(<SyntheticValidationPanel api={client} pollIntervalMs={1} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    await waitFor(() => expect(screen.getAllByRole('button').every((button) => button.hasAttribute('disabled'))).toBe(true));
  });

  it('renders the bounded PASS interpretation', async () => {
    render(<SyntheticValidationPanel api={api()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    expect(await screen.findByText('Contract synthetic đạt; thiết bị vẫn chưa được xác minh.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Lịch sử chạy synthetic' })).toBeInTheDocument();
    for (const marker of ['SIMULATED', 'DEVICE_UNVERIFIED', 'd1_go=false', 'AUTHORITY_NOT_ISSUED']) {
      expect(screen.getByText((_text, element) => element?.tagName === 'P' && Boolean(element.textContent?.includes(marker)))).toBeInTheDocument();
    }
    expect(screen.getAllByText(digest).length).toBeGreaterThanOrEqual(2);
  });

  it('renders persisted NO_GO as technical audit evidence', async () => {
    render(<SyntheticValidationPanel api={api({ createSyntheticRun: vi.fn().mockResolvedValue(terminal('NO_GO')) })} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    expect(await screen.findByText('NO_GO kỹ thuật đã được lưu để đối chiếu.')).toBeInTheDocument();
  });

  it('renders NOT_PERSISTED without claiming an artifact', async () => {
    render(<SyntheticValidationPanel api={api({ createSyntheticRun: vi.fn().mockResolvedValue(terminal('BACKEND_CONTRACT_PASS', false)) })} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    expect(await screen.findByText('Không hình thành được receipt lưu trữ hợp lệ.')).toBeInTheDocument();
  });

  it('does not automatically retry a failed POST', async () => {
    const create = vi.fn().mockRejectedValue(new ApiError(409, undefined, 'RUN_ALREADY_ACTIVE'));
    const failed = render(<SyntheticValidationPanel api={api({ createSyntheticRun: create })} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    expect(await screen.findByText('Không hình thành được receipt lưu trữ hợp lệ.')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(create).toHaveBeenCalledTimes(1);
    failed.unmount();

    const get = vi.fn().mockResolvedValue(queued);
    const mounted = render(<SyntheticValidationPanel api={api({ createSyntheticRun: vi.fn().mockResolvedValue(queued), getSyntheticRun: get })} pollIntervalMs={1} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    await waitFor(() => expect(get).toHaveBeenCalled());
    mounted.unmount();
    const callsAtUnmount = get.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(get).toHaveBeenCalledTimes(callsAtUnmount);

    const authCreate = vi.fn().mockResolvedValue(queued);
    const authGet = vi.fn().mockRejectedValue(new ApiError(401));
    const authLost = render(<SyntheticValidationPanel api={api({ createSyntheticRun: authCreate, getSyntheticRun: authGet })} pollIntervalMs={1} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Chạy preflight mô phỏng 60 giây' }));
    expect(await screen.findByText('Không hình thành được receipt lưu trữ hợp lệ.')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(authCreate).toHaveBeenCalledTimes(1);
    expect(authGet).toHaveBeenCalledTimes(1);
    authLost.unmount();
  });

  it('shows evidence download only for terminal persisted records', async () => {
    const serviceFailure = { ...queued, requestId: 'synrun-11111111111111111111111111111111', jobStatus: 'TERMINAL' as const, serviceFailureCode: 'UNEXPECTED_FAILURE' };
    const notPersisted = { ...terminal('BACKEND_CONTRACT_PASS', false), requestId: 'synrun-22222222222222222222222222222222' };
    const persisted = { ...terminal(), requestId: 'synrun-33333333333333333333333333333333' };
    render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockResolvedValue([queued, notPersisted, serviceFailure, persisted]) })} />);
    expect(await screen.findAllByRole('button', { name: 'Tải bằng chứng synthetic JSON' })).toHaveLength(1);
  });

  it('downloads one safe bundle and displays its full digest and disclosure', async () => {
    const download = vi.fn().mockResolvedValue({
      bytes: new TextEncoder().encode('{"artifact_kind":"M2_SYNTHETIC_EVIDENCE_BUNDLE"}\n'),
      filename: `m2-s2d-${queued.requestId}.json`,
      sha256: digest,
    });
    const createObjectURL = vi.fn().mockReturnValue('blob:synthetic-evidence');
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockResolvedValue([terminal()]), downloadSyntheticEvidence: download })} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Tải bằng chứng synthetic JSON' }));

    const bundleDetails = (await screen.findByText('Bundle SHA-256', { exact: false })).closest('details');
    expect(bundleDetails).not.toBeNull();
    expect(within(bundleDetails!).getByText(digest)).toBeInTheDocument();
    expect(screen.getByText('Bằng chứng mô phỏng — không phải xác minh thiết bị, D1_GO hay quyền thu dữ liệu.')).toBeInTheDocument();
    expect(download).toHaveBeenCalledTimes(1);
    expect(download).toHaveBeenCalledWith(queued.requestId);
    expect(click).toHaveBeenCalledTimes(1);
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-evidence');
  });

  it('allows a persisted technical NO_GO bundle without calling it ready', async () => {
    const download = vi.fn().mockResolvedValue({ bytes: new Uint8Array([123, 125, 10]), filename: `m2-s2d-${queued.requestId}.json`, sha256: digest });
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn().mockReturnValue('blob:no-go') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockResolvedValue([terminal('NO_GO')]), downloadSyntheticEvidence: download })} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Tải bằng chứng synthetic JSON' }));
    expect(await screen.findByText('Đã tải bằng chứng NO_GO kỹ thuật để kiểm tra offline.')).toBeInTheDocument();
    expect(screen.queryByText(/research ready/i)).not.toBeInTheDocument();
  });

  it('surfaces bounded download failure without retrying or hiding run history', async () => {
    const download = vi.fn().mockRejectedValue(new ApiError(409, undefined, 'SYNTHETIC_EVIDENCE_NOT_EXPORTABLE'));
    render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockResolvedValue([terminal()]), downloadSyntheticEvidence: download })} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Tải bằng chứng synthetic JSON' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể tải bằng chứng synthetic hợp lệ.');
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(download).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('heading', { name: 'Lịch sử chạy synthetic' })).toBeInTheDocument();
  });

  it('prevents duplicate download while one request is pending and stops on unmount', async () => {
    const download = vi.fn(() => new Promise<never>(() => undefined));
    const mounted = render(<SyntheticValidationPanel api={api({ listSyntheticRuns: vi.fn().mockResolvedValue([terminal()]), downloadSyntheticEvidence: download })} />);
    const button = await screen.findByRole('button', { name: 'Tải bằng chứng synthetic JSON' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(download).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    mounted.unmount();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(download).toHaveBeenCalledTimes(1);
  });
});
