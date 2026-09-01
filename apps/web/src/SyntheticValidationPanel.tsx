import { useEffect, useRef, useState } from 'react';
import { ApiError, newIdempotencyKey } from './api';
import type { SyntheticReviewApi, SyntheticReviewRun, SyntheticReviewRunKind } from './api';

type Props = { api: SyntheticReviewApi; pollIntervalMs?: number };
type Availability = 'checking' | 'available' | 'missing' | 'unavailable';

function interpretation(run: SyntheticReviewRun): string {
  if (run.serviceFailureCode !== null || run.receipt === null || run.receipt.integrationStatus !== 'PERSISTED') return 'Không hình thành được receipt lưu trữ hợp lệ.';
  if (run.receipt.d1Outcome === 'BACKEND_CONTRACT_PASS') return 'Contract synthetic đạt; thiết bị vẫn chưa được xác minh.';
  if (run.receipt.d1Outcome === 'NO_GO') return 'NO_GO kỹ thuật đã được lưu để đối chiếu.';
  return 'Không hình thành được receipt lưu trữ hợp lệ.';
}

function upsert(runs: SyntheticReviewRun[], record: SyntheticReviewRun): SyntheticReviewRun[] {
  return [record, ...runs.filter((run) => run.requestId !== record.requestId)]
    .sort((left, right) => right.runSequence - left.runSequence);
}

function DigestDetail({ label, digest }: { label: string; digest: string }) {
  return <details className="syntheticDigest">
    <summary>{label}: {digest.slice(0, 12)}…</summary>
    <code>{digest}</code>
  </details>;
}

export function SyntheticValidationPanel({ api, pollIntervalMs = 250 }: Props) {
  const [availability, setAvailability] = useState<Availability>('checking');
  const [active, setActive] = useState(false);
  const [runs, setRuns] = useState<SyntheticReviewRun[]>([]);
  const [message, setMessage] = useState('');
  const [exportingRequestId, setExportingRequestId] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState('');
  const [exportError, setExportError] = useState('');
  const [exportDigests, setExportDigests] = useState<Record<string, string>>({});
  const mounted = useRef(true);
  const operation = useRef(0);
  const exportOperation = useRef(0);

  useEffect(() => {
    mounted.current = true;
    const currentOperation = ++operation.current;
    void api.listSyntheticRuns().then((records) => {
      if (mounted.current && operation.current === currentOperation) {
        setRuns(records);
        setAvailability('available');
      }
    }).catch((error) => {
      if (!mounted.current || operation.current !== currentOperation) return;
      if (error instanceof ApiError && error.status === 404 && error.detail === 'Not Found') setAvailability('missing');
      else setAvailability('unavailable');
    });
    return () => {
      mounted.current = false;
      operation.current += 1;
      exportOperation.current += 1;
    };
  }, [api]);

  const run = async (runKind: SyntheticReviewRunKind) => {
    if (active) return;
    const currentOperation = ++operation.current;
    setActive(true);
    setMessage('');
    try {
      let record = await api.createSyntheticRun(runKind, newIdempotencyKey());
      if (!mounted.current || operation.current !== currentOperation) return;
      setRuns((current) => upsert(current, record));
      const deadline = Date.now() + 30_000;
      while (record.jobStatus !== 'TERMINAL' && Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, pollIntervalMs));
        if (!mounted.current || operation.current !== currentOperation) return;
        record = await api.getSyntheticRun(record.requestId);
        if (!mounted.current || operation.current !== currentOperation) return;
        setRuns((current) => upsert(current, record));
      }
      if (mounted.current && operation.current === currentOperation) {
        setMessage(record.jobStatus === 'TERMINAL' ? interpretation(record) : 'Không hình thành được receipt lưu trữ hợp lệ.');
      }
    } catch (error) {
      if (!mounted.current || operation.current !== currentOperation) return;
      if (error instanceof ApiError && error.status === 409 && error.code === 'SYNTHETIC_RUN_ALREADY_ACTIVE') {
        try {
          const records = await api.listSyntheticRuns();
          if (mounted.current && operation.current === currentOperation) setRuns(records);
        } catch {
          // The bounded conflict remains the only surfaced failure.
        }
      }
      if (mounted.current && operation.current === currentOperation) setMessage('Không hình thành được receipt lưu trữ hợp lệ.');
    } finally {
      if (mounted.current && operation.current === currentOperation) setActive(false);
    }
  };

  const downloadEvidence = async (record: SyntheticReviewRun) => {
    if (exportingRequestId !== null) return;
    const currentOperation = ++exportOperation.current;
    setExportingRequestId(record.requestId);
    setExportMessage('');
    setExportError('');
    let objectUrl: string | null = null;
    try {
      const download = await api.downloadSyntheticEvidence(record.requestId);
      if (!mounted.current || exportOperation.current !== currentOperation) return;
      const blob = new Blob([download.bytes.slice().buffer], { type: 'application/json' });
      objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = download.filename;
      anchor.click();
      setExportDigests((current) => ({ ...current, [record.requestId]: download.sha256 }));
      setExportMessage(record.receipt?.d1Outcome === 'NO_GO'
        ? 'Đã tải bằng chứng NO_GO kỹ thuật để kiểm tra offline.'
        : 'Đã tải bằng chứng synthetic để kiểm tra offline.');
    } catch {
      if (mounted.current && exportOperation.current === currentOperation) {
        setExportError('Không thể tải bằng chứng synthetic hợp lệ.');
      }
    } finally {
      if (objectUrl !== null) URL.revokeObjectURL(objectUrl);
      if (mounted.current && exportOperation.current === currentOperation) {
        setExportingRequestId(null);
      }
    }
  };

  if (availability === 'checking' || availability === 'missing') return null;
  if (availability === 'unavailable') return <section className="syntheticValidationPanel" aria-labelledby="synthetic-validation-unavailable-heading">
    <h2 id="synthetic-validation-unavailable-heading" className="nfcText">Xác minh tích hợp synthetic</h2>
    <p role="alert">Tính năng xác minh synthetic tạm thời không khả dụng.</p>
  </section>;

  return <section className="syntheticValidationPanel" aria-labelledby="synthetic-validation-heading">
    <p className="syntheticAuthorityBanner">MÔ PHỎNG — KHÔNG CAMERA — KHÔNG CẤP QUYỀN THU DỮ LIỆU</p>
    <h2 id="synthetic-validation-heading" className="nfcText">Xác minh tích hợp synthetic</h2>
    <p>Receipt này chỉ đối chiếu contract kỹ thuật bằng fixture mô phỏng; thiết bị và quyền thu dữ liệu vẫn chưa được xác minh.</p>
    <div className="syntheticActions">
      <button className="inkButton" disabled={active} onClick={() => void run('PREFLIGHT_60S')}>Chạy preflight mô phỏng 60 giây</button>
      <button className="quietButton" disabled={active} onClick={() => void run('NOMINAL_20M')}>Chạy nominal mô phỏng 20 phút (18.077 frame tăng tốc)</button>
    </div>
    <p className="syntheticResult" aria-live="polite">{message}</p>
    <p className="syntheticEvidenceDisclosure">Bằng chứng mô phỏng — không phải xác minh thiết bị, D1_GO hay quyền thu dữ liệu.</p>
    {exportMessage && <p className="syntheticResult" aria-live="polite">{exportMessage}</p>}
    {exportError && <p className="syntheticResult" role="alert">{exportError}</p>}
    {runs.length > 0 && <section aria-labelledby="synthetic-history-heading">
      <h3 id="synthetic-history-heading">Lịch sử chạy synthetic</h3>
      <ol className="syntheticHistory">
        {runs.map((record) => <li key={record.requestId}>
          <p>#{record.runSequence} · {record.runKind} · {record.jobStatus}</p>
          <p>{record.receipt?.d1Outcome ?? 'D1_PENDING'}{record.receipt?.d1FailureCode ? ` · ${record.receipt.d1FailureCode}` : ''}</p>
          <p>SIMULATED · DEVICE_UNVERIFIED · d1_go=false · AUTHORITY_NOT_ISSUED</p>
           {record.receipt && <>
            <p>Số observation: {record.receipt.observationCount}</p>
            <DigestDetail label="Receipt digest" digest={record.receipt.resultDigest} />
             {record.receipt.artifactSha256 && <DigestDetail label="Artifact digest" digest={record.receipt.artifactSha256} />}
           </>}
          {record.jobStatus === 'TERMINAL' && record.serviceFailureCode === null && record.receipt?.integrationStatus === 'PERSISTED' && record.receipt.artifactSha256 !== null && <>
            <button
              className="quietButton syntheticEvidenceButton"
              disabled={exportingRequestId !== null}
              onClick={() => void downloadEvidence(record)}
            >Tải bằng chứng synthetic JSON</button>
            {exportDigests[record.requestId] && <DigestDetail label="Bundle SHA-256" digest={exportDigests[record.requestId]} />}
          </>}
         </li>)}
      </ol>
    </section>}
  </section>;
}
