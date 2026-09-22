import { useCallback, useEffect, useRef, useState } from 'react';
import { newIdempotencyKey } from './api';
import './workspace.css';

type RecordData = Record<string, unknown>;
export interface WorkspaceApi {
  workspaceRequest(path: string, init?: RequestInit): Promise<RecordData>;
  workspaceDownload(path: string): Promise<Blob>;
  workspaceImport(file: File, key: string): Promise<RecordData>;
}
const labels: Record<string, string> = { NORMAL: 'Bình thường', BENIGN_CONFOUNDER: 'Cử động thông thường dễ nhầm', PROLONGED_HEAD_DOWN: 'Cúi đầu kéo dài', PROLONGED_SIDE_LOOK: 'Nhìn sang bên kéo dài', NO_PERSON: 'Không thấy người', MULTIPLE_PEOPLE: 'Nhiều người trong khung', UNCERTAIN: 'Chưa đủ bằng chứng' };
const states: Record<string, string> = { DRAFT: 'Chuẩn bị', CONSENT_CONFIRMED: 'Đã ghi nhận đồng ý', PREFLIGHT_READY: 'Sẵn sàng', RECORDING: 'Đang ghi nhận', STOPPED: 'Đã dừng', SEALED: 'Đã niêm phong', FAILED: 'Lỗi kỹ thuật', WITHDRAWN: 'Đã rút dữ liệu' };
const qualityLabels: Record<string, string> = { UNKNOWN: 'Chưa đo', SYNTHETIC: 'Mô phỏng', SUFFICIENT: 'Đủ tín hiệu', INSUFFICIENT: 'Thiếu tín hiệu', TECHNICAL_INSUFFICIENT: 'Thiếu bằng chứng' };
const reviewLabels: Record<string, string> = { UNREVIEWED: 'Chưa duyệt', CONFIRMED: 'Đã xác nhận', REJECTED: 'Đã từ chối', UNCERTAIN: 'Chưa đủ bằng chứng' };
const records = (value: unknown): RecordData[] => Array.isArray(value) ? value.filter((row): row is RecordData => !!row && typeof row === 'object') : [];

export function WorkspacePanel({ api, onLogout }: { api: WorkspaceApi; onLogout: () => void }) {
  const [summary, setSummary] = useState<RecordData>({});
  const [selected, setSelected] = useState<RecordData>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [preview, setPreview] = useState('');
  const previewRef = useRef('');
  const [source, setSource] = useState('AI_RENDERED');
  const [manual, setManual] = useState(false);
  const selectedId = selected?.session_id as string | undefined;
  const load = useCallback(async () => { setSummary(await api.workspaceRequest('')); }, [api]);
  const open = useCallback(async (id: string) => { setSelected(await api.workspaceRequest(`/sessions/${encodeURIComponent(id)}`)); }, [api]);
  useEffect(() => { let active = true; void api.workspaceRequest('').then(value => { if (active) setSummary(value); }).catch(() => { if (active) setMessage('Không thể mở workspace. Kiểm tra chế độ khởi động và đăng nhập.'); }); return () => { active = false; }; }, [api]);
  useEffect(() => { if (!selectedId || selected?.state !== 'RECORDING') return; const timer = window.setInterval(() => { void open(selectedId).catch(() => setMessage('Mất kết nối. Trạng thái hiện tại chưa được xác minh.')); }, 1500); return () => window.clearInterval(timer); }, [open, selectedId, selected?.state]);
  useEffect(() => () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); }, []);
  const run = async (operation: () => Promise<unknown>) => {
    setBusy(true); setMessage('');
    try { await operation(); await load(); }
    catch (error) { const code = error instanceof Error ? error.message : ''; setMessage(`Thao tác chưa hoàn tất. ${code.includes('AUTHORITY') ? 'Chưa có hồ sơ cho phép thu thập; cấu hình hồ sơ đã được phê duyệt bằng công cụ cục bộ.' : 'Kiểm tra điều kiện phiên, kết nối và thử lại.'}`); }
    finally { setBusy(false); }
  };
  const action = (name: string) => run(async () => {
    await api.workspaceRequest(`/sessions/${selectedId}/${name}`, { method: 'POST', headers: { 'Idempotency-Key': newIdempotencyKey() } });
    if (name.startsWith('withdraw') && previewRef.current) { URL.revokeObjectURL(previewRef.current); previewRef.current = ''; setPreview(''); }
    await open(selectedId!);
  });
  const download = (blob: Blob, name: string) => { const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); };
  const model = (summary.model ?? {}) as RecordData;
  return <main className="workspace" aria-label="Workspace nghiên cứu">
    <header className="workspaceHero"><div><p className="eyebrow">PDU / CÔNG CỤ NGHIÊN CỨU</p><h1>Phiên thi & bằng chứng</h1><p>Quan sát tín hiệu, đối chiếu ngữ cảnh, để người đánh giá quyết định.</p></div><button className="quietButton" onClick={onLogout}>Đăng xuất</button></header>
    <div className="workspaceStatus"><span className="statusDot" /> Chạy cục bộ · Video ở lại trên máy · Không thu âm</div>
    {message && <p role="alert" className="workspaceNotice">{message}</p>}
    <div className="workspaceColumns"><aside className="workspaceCard"><p className="eyebrow">01 / CHUẨN BỊ</p><h2>Danh sách phiên</h2><label htmlFor="workspace-source">Nguồn dữ liệu</label><select id="workspace-source" value={source} onChange={e => setSource(e.target.value)}><option value="AI_RENDERED">Mô phỏng kỹ thuật</option><option value="REAL">Nghiên cứu thật — cần hồ sơ phê duyệt</option></select><button className="inkButton" disabled={busy} onClick={() => void run(async () => { const row = await api.workspaceRequest('/sessions', { method: 'POST', headers: { 'Idempotency-Key': newIdempotencyKey() }, body: JSON.stringify({ source_kind: source }) }); await open(String(row.session_id)); })}>Tạo phiên mới</button>
    <ul className="workspaceSessions">{records(summary.sessions).map(row => <li key={String(row.session_id)} className={row.session_id === selectedId ? 'selectedSession' : ''}><strong>{row.source_kind === 'REAL' ? 'Phiên nghiên cứu' : 'Dữ liệu mô phỏng'}</strong><span>{states[String(row.state)] ?? String(row.state)}</span><button className="quietButton" disabled={busy} onClick={() => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); previewRef.current = ''; setPreview(''); void run(() => open(String(row.session_id))); }}>Mở phiên {String(row.session_id).slice(0, 8)}</button></li>)}</ul>{records(summary.sessions).length === 0 && <p className="muted">Chưa có phiên. Bắt đầu bằng một phiên mô phỏng để kiểm tra toàn bộ quy trình.</p>}
    </aside><section className="workspaceCard workspaceDetail"><p className="eyebrow">02 / GHI NHẬN & ĐỐI CHIẾU</p>{!selected ? <div className="workspaceEmpty"><h2>Một phiên, đầy đủ dấu vết</h2><p>Chọn phiên bên trái để chuẩn bị, kiểm tra tín hiệu và duyệt sự kiện sau khi niêm phong.</p><ol><li>Ghép mã trên màn hình bài thi.</li><li>Kiểm tra điều kiện rồi bắt đầu ghi nhận.</li><li>Dừng, niêm phong, duyệt và khóa dữ liệu.</li></ol></div> : <>
      <h2>{states[String(selected.state)] ?? String(selected.state)}</h2><p className="workspaceNotice">{selected.source_kind === 'REAL' ? 'Thu thập chỉ được mở khi hồ sơ phê duyệt, đồng ý, lưu trữ và thời hạn lưu đều hợp lệ.' : 'MÔ PHỎNG — không phải dữ liệu camera hoặc kết quả nghiên cứu.'}</p>
      {typeof selected.pairing_code === 'string' && <p className="workspacePairing">Mã ghép cặp <strong>{selected.pairing_code}</strong><small>Mở màn hình bài thi và nhập mã này.</small></p>}
      <div className="workspaceActions"><button disabled={busy || !['DRAFT', 'CONSENT_CONFIRMED', 'PREFLIGHT_READY'].includes(String(selected.state))} onClick={() => void action('preflight')}>Kiểm tra trước phiên</button><button className="inkButton" disabled={busy || selected.state !== 'PREFLIGHT_READY'} onClick={() => void action('start')}>Bắt đầu</button><button disabled={busy || selected.state !== 'RECORDING'} onClick={() => void action('stop')}>Dừng</button><button disabled={busy || !['STOPPED', 'RECORDING'].includes(String(selected.state))} onClick={() => void action('seal')}>Niêm phong</button><button disabled={busy} onClick={() => void run(() => open(selectedId!))}>Cập nhật</button></div>
      <div className="workspaceMetrics"><div><span>Sự kiện</span><strong>{String(selected.event_count ?? records(selected.events).length)}</strong></div><div><span>Chất lượng</span><strong>{qualityLabels[String(selected.quality_state)] ?? 'Chưa đo'}</strong></div><div><span>Dữ liệu</span><strong>{selected.locked ? 'Đã khóa' : 'Chưa khóa'}</strong></div></div>
      {selected.failure_reason && <p role="alert">Thiếu bằng chứng kỹ thuật: {String(selected.failure_reason)}</p>}
      {selected.state === 'RECORDING' && <LiveSkeleton live={(selected.live ?? {}) as RecordData} />}
      <h3>Duyệt sự kiện</h3><p className="muted">Nhãn mô tả điều quan sát được; không kết luận ý định hoặc gian lận.</p>
      {records(selected.events).map(event => <EventReview key={`${String(event.event_id)}-${String(event.revision)}`} event={event} disabled={busy || selected.state !== 'SEALED' || !!selected.locked} onSave={payload => run(async () => { await api.workspaceRequest(`/sessions/${selectedId}/decision`, { method: 'PUT', headers: { 'Idempotency-Key': newIdempotencyKey() }, body: JSON.stringify(payload) }); await open(selectedId!); })} />)}
      {records(selected.events).length === 0 && <p>Chưa có sự kiện được lưu.</p>}
      <button disabled={busy || selected.state !== 'SEALED' || !!selected.locked} onClick={() => setManual(!manual)}>Gán nhãn đoạn video khác</button>
      {manual && <EventReview key={`manual-${selectedId}-${String(selected.revision)}`} event={{ event_id: '', research_label: 'UNCERTAIN', revision: selected.revision, start_ms: 0, end_ms: 1000 }} disabled={busy || selected.state !== 'SEALED' || !!selected.locked} onSave={payload => run(async () => { await api.workspaceRequest(`/sessions/${selectedId}/decision`, { method: 'PUT', headers: { 'Idempotency-Key': newIdempotencyKey() }, body: JSON.stringify(payload) }); setManual(false); await open(selectedId!); })} />}
      <button disabled={busy || selected.state !== 'SEALED'} onClick={() => download(new Blob([JSON.stringify({ session_id: selectedId, report: selected.report, reviews: selected.review_history }, null, 2)], { type: 'application/json' }), 'pdu-bao-cao-duyet-local.json')}>Lưu báo cáo duyệt cục bộ</button>
      <div className="workspaceActions"><button disabled={busy || selected.state !== 'SEALED'} onClick={() => void run(async () => { const blob = await api.workspaceDownload(`/sessions/${selectedId}/preview`); if (previewRef.current) URL.revokeObjectURL(previewRef.current); const url = URL.createObjectURL(blob); previewRef.current = url; setPreview(url); })}>Xem video cục bộ</button><button disabled={busy || selected.state !== 'SEALED' || !!selected.locked} onClick={() => void action('lock')}>Khóa dữ liệu đã duyệt</button><button className="inkButton" disabled={busy || !selected.locked || selected.state !== 'SEALED'} onClick={() => void run(async () => download(await api.workspaceDownload(`/sessions/${selectedId}/export`), 'pdu-pose-export.zip'))}>Xuất dữ liệu pose</button></div>
      {preview && <video className="workspaceVideo" src={preview} controls preload="metadata" aria-label="Video cục bộ đã niêm phong" />}
      {selected.source_kind !== 'REAL' && <details><summary>Dọn dữ liệu thử của phiên</summary><p>Xóa artifact mô phỏng của phiên này và giữ biên bản đối soát.</p><button disabled={busy || selected.state === 'RECORDING' || selected.state === 'WITHDRAWN'} onClick={() => void action('withdraw-test')}>Rút và xóa dữ liệu thử</button></details>}
      {selected.source_kind === 'REAL' && <details><summary>Rút dữ liệu theo hồ sơ cục bộ</summary><p>Thực hiện quyết định xóa hoặc cách ly đã được ghi trong hồ sơ rút dữ liệu. Bản export đã tải cần được đối soát riêng.</p><button disabled={busy || selected.state === 'DRAFT' || selected.state === 'WITHDRAWN'} onClick={() => void action('withdraw')}>Thực hiện hồ sơ rút dữ liệu</button></details>}
    </>}</section></div>
    <section className="workspaceCard workspaceModels"><div><p className="eyebrow">03 / MÔ HÌNH</p><h2>{model.status === 'MODEL_UNAVAILABLE' || !model.status ? 'Chưa có mô hình' : 'Mô hình cục bộ'}</h2><p>Gói ZIP được kiểm tra hash, phiên bản và đầu ra mẫu trước khi kích hoạt. Gói smoke và luật minh họa chỉ dùng cho mô phỏng; luật nghiên cứu cần chính sách đã chốt.</p><code>{String(model.model_version ?? model.status ?? 'MODEL_UNAVAILABLE')}</code></div><label className="modelUpload">Nhập gói model ZIP<input type="file" accept=".zip,application/zip" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) void run(() => api.workspaceImport(file, newIdempotencyKey())); e.target.value = ''; }} /></label></section>
  </main>;
}

function LiveSkeleton({ live }: { live: RecordData }) {
  const poses = Array.isArray(live.landmarks) ? live.landmarks : [];
  const edges = [[0, 11], [0, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28]];
  return <figure className="workspaceSkeleton"><figcaption>Tín hiệu tư thế · {live.source_kind === 'REAL' ? 'Camera cục bộ' : 'Mô phỏng'} · Khung {String(live.frame_seq ?? 'chưa có')}</figcaption><svg viewBox="0 0 640 360" role="img" aria-label="Skeleton trực tiếp, không hiển thị video hoặc danh tính"><rect width="640" height="360" fill="#162723" />{poses.map((raw, index) => { const points = records(raw); return <g key={index} stroke="#95dfad" fill="#d8fbe1">{edges.map(([a, b]) => points[a] && points[b] ? <line key={`${a}-${b}`} x1={Number(points[a].x) * 640} y1={Number(points[a].y) * 360} x2={Number(points[b].x) * 640} y2={Number(points[b].y) * 360} strokeWidth="2" /> : null)}{points.map((point, i) => <circle key={i} cx={Number(point.x) * 640} cy={Number(point.y) * 360} r="3" />)}</g>; })}</svg></figure>;
}

function EventReview({ event, disabled, onSave }: { event: RecordData; disabled: boolean; onSave: (payload: RecordData) => Promise<void> }) {
  const [label, setLabel] = useState(String(event.label ?? event.research_label ?? 'UNCERTAIN'));
  const [status, setStatus] = useState('CONFIRMED');
  const [start, setStart] = useState(Number(event.start_ms ?? 0));
  const [end, setEnd] = useState(Number(event.end_ms ?? 6000));
  const [reason, setReason] = useState('');
  return <form className="workspaceEvent" onSubmit={e => { e.preventDefault(); void onSave({ event_id: event.event_id, label: status === 'UNCERTAIN' ? 'UNCERTAIN' : label, review_status: status, start_ms: start, end_ms: end, reason, expected_revision: event.revision ?? 0 }); }}><p><strong>{labels[String(event.label ?? event.research_label)] ?? 'Thiếu bằng chứng kỹ thuật'}</strong> · {reviewLabels[String(event.review_status ?? 'UNREVIEWED')] ?? 'Chưa duyệt'}</p><fieldset disabled={disabled}><legend>Quyết định của người đánh giá</legend><label>Nhãn<select value={label} onChange={e => setLabel(e.target.value)}>{Object.entries(labels).map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label><label>Kết luận duyệt<select value={status} onChange={e => setStatus(e.target.value)}><option value="CONFIRMED">Xác nhận</option><option value="REJECTED">Từ chối</option><option value="UNCERTAIN">Chưa đủ bằng chứng</option></select></label><label>Bắt đầu (ms)<input type="number" min="0" value={start} onChange={e => setStart(Number(e.target.value))} /></label><label>Kết thúc (ms)<input type="number" min={start + 1} value={end} onChange={e => setEnd(Number(e.target.value))} /></label><label>Lý do<input value={reason} required maxLength={500} onChange={e => setReason(e.target.value)} /></label><button disabled={!reason.trim() || end <= start}>Lưu quyết định</button></fieldset></form>;
}
