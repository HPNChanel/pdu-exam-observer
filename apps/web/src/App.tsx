import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, BrowserEventStream, DemoApiClient, HttpApiClient, isReviewerAuthLossSource, newIdempotencyKey, noEventStream } from './api';
import type { AnswerIntent, ApiClient, EventStream, ResearchApi, ReviewerEvent, SessionSnapshot, SessionState, StreamMessage } from './api';
import './styles.css';
import { ResearchPreparation } from './ResearchPreparation';
import { WorkspacePanel } from './WorkspacePanel';

type AppProps = { route?: '/exam' | '/monitor'; api?: ApiClient; events?: EventStream; initialReviewer?: boolean; demoMode?: boolean };
const questions = [{ id: 'q1', prompt: 'Một ngăn xếp (stack) tuân theo nguyên tắc nào?', choices: ['FIFO', 'LIFO', 'Chia để trị', 'Ngẫu nhiên'] }, { id: 'q2', prompt: 'Độ phức tạp tìm kiếm nhị phân trên mảng đã sắp xếp là?', choices: ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)'] }, { id: 'q3', prompt: 'Cấu trúc dữ liệu nào phù hợp cho hàng đợi?', choices: ['Queue', 'Tree', 'Graph', 'Set'] }];
const defaultApi = new HttpApiClient(); const demoApi = new DemoApiClient();
const normalizeVietnameseText = (value: string) => value.normalize('NFC');
const formatTime = (seconds: number | null) => { if (seconds === null) return '--:--'; return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`; };
const errorText = (error: unknown, action: string) => error instanceof ApiError && error.status === 401 ? 'PIN không hợp lệ.' : error instanceof ApiError && error.status === 429 ? `Thử lại sau ${error.retryAfter ?? '?'} giây.` : `${action}. Vui lòng thử lại.`;

export function App({ route = window.location.pathname === '/monitor' ? '/monitor' : '/exam', api = defaultApi, events, initialReviewer = false, demoMode }: AppProps) {
  const isDemo = demoMode ?? new URLSearchParams(window.location.search).get('demo') === '1'; const activeApi = isDemo ? demoApi : api; const [health, setHealth] = useState<'checking' | 'live' | 'failed'>('checking');
  const checkHealth = () => { setHealth('checking'); void activeApi.health().then(() => setHealth('live')).catch(() => setHealth('failed')); };
  useEffect(() => { void activeApi.health().then(() => setHealth('live')).catch(() => setHealth('failed')); }, [activeApi]);
  return <div className="appShell">{isDemo && <p className="offlineBanner demoBanner" role="status">DEMO NGOẠI TUYẾN - dữ liệu minh họa, không phải phiên nghiên cứu hay dữ liệu camera.</p>}{health === 'failed' ? <main className="blockingSheet" aria-label="Không thể kết nối hệ thống"><h1>Không thể kết nối hệ thống cục bộ</h1><p>Không có dữ liệu demo tự động và phiên thi không được mở.</p><button className="inkButton" onClick={checkHealth}>Thử kết nối lại</button></main> : route === '/monitor' ? <Monitor api={activeApi} events={events} initialReviewer={initialReviewer} health={health} /> : <Exam api={activeApi} health={health} />}</div>;
}
function AppHeader({ title, subtitle }: { title: string; subtitle: string }) { return <header className="appHeader"><p className="eyebrow">PDU / NGHIÊN CỨU</p><h1 className="nfcText">{normalizeVietnameseText(title)}</h1><p>{normalizeVietnameseText(subtitle)}</p></header>; }

function Exam({ api, health }: { api: ApiClient; health: 'checking' | 'live' | 'failed' }) {
  const [pairingCode, setPairingCode] = useState(''); const [sessionId, setSessionId] = useState<string>(); const [snapshot, setSnapshot] = useState<SessionSnapshot>(); const [current, setCurrent] = useState(0); const [answers, setAnswers] = useState<Record<string, string>>({}); const [pendingAnswer, setPendingAnswer] = useState<(AnswerIntent & { key: string })>(); const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle'); const [remaining, setRemaining] = useState<number | null>(null); const [submitOpen, setSubmitOpen] = useState(false); const [submitKey, setSubmitKey] = useState<string>(); const [submitError, setSubmitError] = useState('');
  const recording = snapshot?.state === 'RECORDING' && !snapshot.submitted;
  useEffect(() => {
    if (!recording || !api.focus) return;
    const reportFocus = () => { void api.focus!(document.visibilityState === 'visible' && document.hasFocus()).catch(() => undefined); };
    reportFocus();
    const interval = window.setInterval(reportFocus, 1000);
    window.addEventListener('focus', reportFocus); window.addEventListener('blur', reportFocus); document.addEventListener('visibilitychange', reportFocus);
    return () => { window.clearInterval(interval); window.removeEventListener('focus', reportFocus); window.removeEventListener('blur', reportFocus); document.removeEventListener('visibilitychange', reportFocus); };
  }, [api, recording]);
  const applySnapshot = (next: SessionSnapshot) => { setSnapshot(next); setRemaining(next.remainingSeconds); };
  useEffect(() => { if (!recording) return; const timer = window.setInterval(() => setRemaining((value) => value === null ? null : Math.max(0, value - 1)), 1000); return () => window.clearInterval(timer); }, [recording]);
  useEffect(() => { if (!sessionId || !['PREFLIGHT_READY', 'RECORDING'].includes(snapshot?.state ?? '')) return; const timer = window.setInterval(() => void api.status().then(applySnapshot).catch(() => undefined), 5000); return () => window.clearInterval(timer); }, [api, sessionId, snapshot?.state]);
  const refresh = async () => { applySnapshot(await api.status()); };
  const save = async (intent: AnswerIntent & { key: string }) => { setSaveState('saving'); try { const result = await api.answer(intent, intent.key); if (!result.accepted) throw new Error('not accepted'); setSaveState('saved'); } catch { setSaveState('error'); } };
  const choose = (value: string) => { const question = questions[current]; const intent = { answerId: `${question.id}-${value}`, questionId: question.id, value, key: newIdempotencyKey() }; setAnswers((existing) => ({ ...existing, [question.id]: value })); setPendingAnswer(intent); void save(intent); };
  const submit = async () => { const key = submitKey ?? newIdempotencyKey(); setSubmitKey(key); setSubmitError(''); try { const result = await api.submit(key); if (!result.submitted) throw new Error('not submitted'); setSnapshot((currentSnapshot) => currentSnapshot ? { ...currentSnapshot, submitted: true } : currentSnapshot); setSubmitOpen(false); } catch { setSubmitError('Không thể nộp bài. Vui lòng thử lại; yêu cầu sẽ dùng cùng mã idempotency.'); } };
  return <><AppHeader title="Bài thi thử" subtitle="Không gian làm bài độc lập" /><main className="examSurface reveal" aria-label="Bài thi thử">{!sessionId ? <section className="pairingSheet" aria-label="Ghép cặp phiên thi"><label htmlFor="pairing-code">Mã ghép cặp do người đánh giá cung cấp</label><input id="pairing-code" value={pairingCode} onChange={(event) => setPairingCode(event.target.value)} /><button className="inkButton" disabled={!pairingCode || health !== 'live'} onClick={() => void api.pair(pairingCode).then(({ sessionId: id }) => { setSessionId(id); return api.status(); }).then(applySnapshot)}>Ghép cặp phiên</button></section> : <>{snapshot?.state === 'DRAFT' && <section className="lifecycleSheet"><h2>Xác nhận đồng ý tham gia</h2><p>Chỉ tiếp tục sau khi bạn đã đọc và đồng ý quy trình nghiên cứu.</p><button className="inkButton" onClick={() => void api.consent(sessionId).then(applySnapshot)}>Xác nhận đồng ý</button></section>}{snapshot?.state === 'CONSENT_CONFIRMED' && <section className="lifecycleSheet"><h2>Kiểm tra trước khi làm bài</h2><p>Kiểm tra này chỉ xác nhận trạng thái kỹ thuật, không đưa ra kết luận hành vi.</p><button className="inkButton" onClick={() => void api.preflight(sessionId).then(applySnapshot)}>Hoàn tất kiểm tra trước thi</button></section>}{snapshot && !recording && !snapshot.submitted && snapshot.state !== 'DRAFT' && snapshot.state !== 'CONSENT_CONFIRMED' && <section className="lifecycleSheet" aria-live="polite"><h2>{snapshot.state === 'PREFLIGHT_READY' ? 'Đợi người đánh giá bắt đầu ghi nhận' : 'Phiên chưa sẵn sàng'}</h2><p>Trạng thái hiện tại: {snapshot.state}.</p><button className="quietButton" onClick={() => void refresh()}>Cập nhật trạng thái phiên</button></section>}{recording && <><section className="examMeta" aria-label="Thông tin bài thi"><p>Thời gian còn lại <strong>{formatTime(remaining)}</strong></p><p className="disclosure">Phiên làm bài có ghi nhận dữ liệu kỹ thuật tối thiểu cho nghiên cứu đã được đồng ý.</p></section><section className="questionPaper" aria-labelledby="question-title"><p className="questionCounter">Câu {current + 1} / {questions.length}</p><h2 id="question-title" className="nfcText">{normalizeVietnameseText(questions[current].prompt)}</h2><div className="answerGrid" role="radiogroup" aria-label="Các đáp án">{questions[current].choices.map((choice, index) => { const letter = String.fromCharCode(65 + index); return <button className={answers[questions[current].id] === letter ? 'answer selected' : 'answer'} key={letter} role="radio" aria-checked={answers[questions[current].id] === letter} aria-label={`Chọn đáp án ${letter}`} onClick={() => choose(letter)}><span>{letter}</span>{choice}</button>; })}</div></section><nav className="examNavigation" aria-label="Điều hướng câu hỏi"><button className="quietButton" disabled={current === 0} onClick={() => setCurrent((value) => value - 1)}>Câu trước</button><p aria-live="polite">{saveState === 'saving' ? 'Đang lưu câu trả lời...' : saveState === 'saved' ? 'Đã lưu' : saveState === 'error' ? <>Không thể lưu câu trả lời. <button className="linkButton" onClick={() => pendingAnswer && void save(pendingAnswer)}>Thử lưu lại</button></> : 'Chưa có thay đổi'}</p><button className="inkButton" disabled={current === questions.length - 1} onClick={() => setCurrent((value) => value + 1)}>Câu tiếp theo</button></nav><button className="orangeButton submitButton" onClick={() => setSubmitOpen(true)}>Nộp bài</button></>}{snapshot?.submitted && <section className="lifecycleSheet" aria-live="polite"><h2>Bài làm đã được nộp</h2><p>Không thể thay đổi đáp án sau khi nộp.</p></section>}{submitOpen && <section className="confirmation" role="alertdialog" aria-modal="true" aria-labelledby="submit-title"><h2 id="submit-title">Xác nhận nộp bài</h2><p>Bạn sẽ không thể thay đổi đáp án sau khi nộp.</p>{submitError && <p role="alert">{submitError}</p>}<button className="quietButton" onClick={() => setSubmitOpen(false)}>Quay lại</button><button className="orangeButton" onClick={() => void submit()}>Xác nhận nộp bài</button></section>}</>}</main><footer className={health === 'live' ? 'technicalStatus' : 'technicalStatus pending'} role="status" aria-label="Trạng thái kỹ thuật"><span aria-hidden="true" />{health === 'live' ? 'Kết nối hệ thống cục bộ đã được xác nhận' : 'Đang kiểm tra kết nối hệ thống cục bộ'}</footer></>;
}

const phaseFor = (state: SessionState | undefined) => {
  switch (state) {
    case 'PREFLIGHT_READY': return { state, title: 'Sẵn sàng ghi nhận', detail: 'Đã hoàn tất kiểm tra; chờ người đánh giá bắt đầu.', tone: 'ready' };
    case 'RECORDING': return { state, title: 'Đang ghi nhận', detail: 'Phiên đang ghi nhận bằng chứng kỹ thuật cục bộ.', tone: 'recording' };
    case 'SEALED': return { state, title: 'Phiên đã niêm phong', detail: 'Phiên đã kết thúc; các hành động thay đổi dữ liệu bị khóa.', tone: 'sealed' };
    case 'CONSENT_CONFIRMED': return { state, title: 'Chờ kiểm tra trước thi', detail: 'Đã có đồng ý; chờ ứng viên hoàn tất kiểm tra.', tone: 'waiting' };
    case 'DRAFT': return { state, title: 'Chờ ghép cặp', detail: 'Tạo phiên và cung cấp mã ghép cặp cho ứng viên.', tone: 'waiting' };
    default: return { state: undefined, title: 'Chờ tạo phiên', detail: 'Chưa có phiên nghiên cứu đang hoạt động.', tone: 'waiting' };
  }
};

function Monitor({ api, events, initialReviewer, health }: { api: ApiClient; events?: EventStream; initialReviewer: boolean; health: 'checking' | 'live' | 'failed' }) {
  const [reviewer, setReviewer] = useState(initialReviewer ? 'Nghiên cứu viên' : '');
  const [pin, setPin] = useState('');
  const [loginError, setLoginError] = useState('');
  const [session, setSession] = useState<{ id: string; pairingCode: string }>();
  const [snapshot, setSnapshot] = useState<SessionSnapshot>();
  const [eventList, setEventList] = useState<ReviewerEvent[]>([]);
  const [streamStatus, setStreamStatus] = useState<'connected' | 'reconnecting'>('reconnecting');
  const [replayState, setReplayState] = useState<'idle' | 'pending' | 'success' | 'error'>('idle');
  const pinInputRef = useRef<HTMLInputElement>(null);
  const clearReviewerAfterAuthLoss = () => { setReviewer(''); setPin(''); setSession(undefined); setSnapshot(undefined); setEventList([]); setReplayState('idle'); setLoginError('Phiên đăng nhập đã hết hạn. Vui lòng nhập lại PIN.'); };

  useEffect(() => {
    if (!isReviewerAuthLossSource(api)) return;
    return api.onReviewerAuthLoss(clearReviewerAfterAuthLoss);
  }, [api]);

  useEffect(() => {
    if (initialReviewer) return;
    let current = true;
    void api.reviewerSession().then(({ reviewer: restored }) => {
      if (current) setReviewer(restored);
    }).catch(() => {
      if (current) setReviewer('');
    });
    return () => { current = false; };
  }, [api, initialReviewer]);

  useEffect(() => {
    if (reviewer) return;
    const scrollTo = window.scrollTo as typeof window.scrollTo & { mock?: unknown };
    const isJsdomShim = navigator.userAgent.includes('jsdom') && !('mock' in scrollTo);
    if (!isJsdomShim) scrollTo({ top: 0, left: 0, behavior: 'auto' });
    const focusTimer = window.setTimeout(() => pinInputRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [reviewer]);

  const eventStream = useMemo(() => events ?? (session ? new BrowserEventStream(session.id) : noEventStream), [events, session]);
  useEffect(() => eventStream.subscribe((message: StreamMessage) => {
    if (message.kind === 'snapshot') setSnapshot(message.snapshot);
    else setEventList((items) => items.some((item) => item.eventSeq === message.event.eventSeq) ? items : [...items, message.event]);
  }, setStreamStatus, () => {
    setReviewer('');
    setPin('');
    setSession(undefined);
    setSnapshot(undefined);
    setEventList([]);
    setReplayState('idle');
    setLoginError('Phiên đăng nhập đã hết hạn. Vui lòng nhập lại PIN.');
  }), [eventStream]);

  const login = async () => { setLoginError(''); try { const authenticated = await api.login(pin); setPin(''); setReviewer(authenticated.reviewer); } catch (error) { setLoginError(errorText(error, 'Không thể đăng nhập')); } };
  const create = async () => { const created = await api.createSession(); setSession({ id: created.id, pairingCode: created.pairingCode }); setSnapshot(created.snapshot); setEventList([]); setReplayState('idle'); };
  const refresh = async () => { if (session) setSnapshot(await api.snapshot(session.id)); };
  const replay = async () => { if (!session || snapshot?.state === 'SEALED') return; setReplayState('pending'); try { await api.replay(session.id); setReplayState('success'); } catch { setReplayState('error'); } };
  const logout = async () => { try { await api.logout(); } finally { setReviewer(''); setPin(''); setSession(undefined); setSnapshot(undefined); setEventList([]); setReplayState('idle'); } };

  if (!reviewer) return <><AppHeader title="Bàn quan sát" subtitle="Chỉ dành cho người đánh giá nghiên cứu" /><main className="loginSheet reveal" aria-labelledby="reviewer-auth-heading"><h2 id="reviewer-auth-heading" className="nfcText">Xác thực người đánh giá</h2><p id="reviewer-auth-description" role="status">Nhập mã PIN để mở bàn quan sát cục bộ.</p><label htmlFor="reviewer-pin">Mã PIN người đánh giá</label><input ref={pinInputRef} id="reviewer-pin" type="password" inputMode="numeric" aria-describedby="reviewer-auth-description" value={pin} onChange={(event) => setPin(event.target.value)} /><button className="inkButton" disabled={health !== 'live'} onClick={() => void login()}>Mở bàn quan sát</button>{loginError && <p role="alert">{loginError}</p>}<p>PIN chỉ xác minh trong phiên trình duyệt hiện tại.</p></main></>;

  const phase = phaseFor(snapshot?.state);
  if (new URLSearchParams(window.location.search).get('workspace') === '1' && api instanceof HttpApiClient) return <WorkspacePanel api={api} onLogout={() => void logout()} />;
  const canStart = snapshot?.state === 'PREFLIGHT_READY';
  const canStop = snapshot?.state === 'RECORDING';
  const showPairingCode = Boolean(session) && snapshot?.state !== 'SEALED';
  return <><AppHeader title="Bàn quan sát" subtitle={`Phiên cục bộ của ${reviewer}`} /><main className="monitorSurface reveal" aria-label="Bàn quan sát"><section className="sessionControls" aria-labelledby="phase-heading"><div className={`phaseBanner phaseBanner--${phase.tone}`}><p className="eyebrow">TRẠNG THÁI PHIÊN</p><h2 id="phase-heading" className="nfcText">{phase.title}</h2><p>{phase.detail}</p>{phase.state && <strong>{phase.state}</strong>}</div><div className="monitorActions"><button className="inkButton" onClick={() => void create()}>Tạo phiên</button>{session && <><button className="quietButton" onClick={() => void refresh()}>Cập nhật phiên</button><button className="inkButton" disabled={!canStart} onClick={() => void api.start(session.id).then(setSnapshot)}>Bắt đầu ghi nhận</button><button className="orangeButton" disabled={!canStop} onClick={() => void api.stop(session.id).then(setSnapshot)}>Dừng phiên</button><button className="quietButton" disabled={snapshot?.state === 'SEALED' || replayState === 'pending'} onClick={() => void replay()}>Phát lại dữ liệu mô phỏng</button></>}<button className="quietButton" onClick={() => void logout()}>Đăng xuất</button></div>{session && <>{showPairingCode ? <p className={`pairingCode ${snapshot?.state === 'RECORDING' ? 'pairingCode--demoted' : ''}`}><span>{snapshot?.state === 'RECORDING' ? 'Mã ghép cặp đã dùng' : 'Mã ghép cặp'}</span><strong>{session.pairingCode}</strong></p> : <p className="pairingCode pairingCode--consumed">Mã ghép cặp đã dùng và không hiển thị sau khi niêm phong.</p>}<p className="technicalNote">Không hiển thị camera hoặc video trực tiếp; đây là trạng thái kỹ thuật của phiên.</p>{snapshot?.state === 'SEALED' ? <p className="replayStatus" aria-live="polite">Phiên đã niêm phong; không thể phát lại dữ liệu mô phỏng.</p> : replayState === 'pending' ? <p className="replayStatus" aria-live="polite">Đang yêu cầu phát dữ liệu mô phỏng từ hệ thống cục bộ.</p> : replayState === 'success' ? <p className="replayStatus" aria-live="polite">Yêu cầu phát dữ liệu mô phỏng đã được gửi; thẻ chỉ xuất hiện khi luồng sự kiện trả về.</p> : replayState === 'error' ? <p className="replayStatus" role="alert">Không thể yêu cầu phát dữ liệu mô phỏng. Vui lòng thử lại.</p> : null}</>}</section><ResearchPreparation api={api as unknown as ResearchApi} /><section className="eventRail" aria-labelledby="events-heading"><div className="railHeading"><div><p className="eyebrow">DÒNG SỰ KIỆN</p><h2 id="events-heading" className="nfcText">Quan sát cần đối chiếu</h2></div><p className={streamStatus === 'connected' ? 'stream good' : 'stream'}>{streamStatus === 'connected' ? 'Luồng sự kiện đang kết nối' : 'Đang kết nối lại luồng sự kiện'}</p></div><p className="eventDisclosure">Dữ liệu mô phỏng, nếu được yêu cầu, chỉ đến từ luồng sự kiện; không phải camera hoặc mô hình trực tiếp.</p><ol className="eventList" aria-live="polite">{eventList.length === 0 && <li className="emptyEvent">Chưa có sự kiện để đối chiếu.</li>}{eventList.map((event) => <li key={event.id} aria-label={`Sự kiện ${event.title}`} className={event.kind === 'technical' ? 'technicalEvent' : 'signalEvent'}><time>Thứ tự #{event.eventSeq}</time><div><strong>{event.title}</strong><p>{event.confidence === null ? `Trạng thái tin cậy: ${event.confidenceStatus}` : `Độ tin cậy ${Math.round(event.confidence * 100)}%`} · {event.durationSeconds ? `${event.durationSeconds} giây` : 'Không ghi nhận thời lượng'}</p><small>Tín hiệu đóng góp: {event.signals.join(', ')}</small></div></li>)}</ol></section></main></>;
}
