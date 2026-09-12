import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react/dist/csr/ArrowRight";
import { Camera } from "@phosphor-icons/react/dist/csr/Camera";
import { CameraSlash } from "@phosphor-icons/react/dist/csr/CameraSlash";
import { Check } from "@phosphor-icons/react/dist/csr/Check";
import { CheckCircle } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { ClockCounterClockwise } from "@phosphor-icons/react/dist/csr/ClockCounterClockwise";
import { GearSix } from "@phosphor-icons/react/dist/csr/GearSix";
import { IdentificationCard } from "@phosphor-icons/react/dist/csr/IdentificationCard";
import { LockKeyOpen } from "@phosphor-icons/react/dist/csr/LockKeyOpen";
import { Pause } from "@phosphor-icons/react/dist/csr/Pause";
import { Play } from "@phosphor-icons/react/dist/csr/Play";
import { ShieldCheck } from "@phosphor-icons/react/dist/csr/ShieldCheck";
import { Trash } from "@phosphor-icons/react/dist/csr/Trash";
import { UserPlus } from "@phosphor-icons/react/dist/csr/UserPlus";
import { UsersThree } from "@phosphor-icons/react/dist/csr/UsersThree";
import { Warning } from "@phosphor-icons/react/dist/csr/Warning";
import { X } from "@phosphor-icons/react/dist/csr/X";
import "@fontsource-variable/manrope";

const fallbackEvents = [
  { timestamp: "09:41:21", status: "GRANTED", name: "Daniel Avery", distance: 0.013, location: "Lobby / North" },
  { timestamp: "09:40:58", status: "GRANTED", name: "Maya Chen", distance: 0.026, location: "Lobby / North" },
  { timestamp: "09:40:35", status: "GRANTED", name: "Ethan Cole", distance: 0.041, location: "Lobby / North" },
  { timestamp: "09:39:12", status: "DENIED", name: "Unknown visitor", distance: 0.714, location: "Lobby / North" },
];

const navItems = [
  ["gateway", Camera, "Gateway"], ["identities", UsersThree, "Identities"],
  ["activity", ClockCounterClockwise, "Activity"], ["settings", GearSix, "Settings"],
];

function formatTime(value) {
  if (!value) return "—";
  if (/^\d{2}:\d{2}/.test(value)) return value.slice(0, 8);
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function statusMeta(status) {
  const states = {
    VERIFIED: ["Identity verified", "Liveness passed · Access granted", "verified"],
    GRANTED: ["Access granted", "Identity and liveness confirmed", "verified"],
    DENIED: ["Access denied", "Identity does not match", "denied"],
    SPOOF_SUSPECTED: ["Spoof suspected", "Live presence could not be confirmed", "denied"],
    SCANNING: ["Verifying identity", "Blink naturally to confirm liveness", "scanning"],
    NO_FACE: ["Ready to verify", "Step into the camera view", "idle"],
    PAUSED: ["Camera paused", "Resume when the gate is attended", "idle"],
    OFFLINE: ["Camera is offline", "Start the camera or explore demo mode", "idle"],
  };
  return states[status] || states.OFFLINE;
}

async function api(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function Header({ active, setActive, system, now }) {
  return <header className="topbar">
    <button className="brand" onClick={() => setActive("gateway")} aria-label="Cereberus home"><span className="brand-mark" aria-hidden="true"><ShieldCheck weight="duotone" /></span><span>CEREBERUS</span></button>
    <nav className="main-nav" aria-label="Primary navigation">{navItems.map(([id, Icon, label]) => <button key={id} className={active === id ? "nav-button active" : "nav-button"} aria-current={active === id ? "page" : undefined} onClick={() => setActive(id)}><Icon weight={active === id ? "fill" : "regular"} /><span>{label}</span></button>)}</nav>
    <div className="topbar-meta"><span className={system.backend ? "live-dot" : "live-dot offline"} /><span>{system.backend ? "System nominal" : "Local mode"}</span><time>{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>
  </header>;
}

function ScanOverlay({ result, demoMode }) {
  const [title, detail, tone] = statusMeta(result.status);
  const box = result.box_normalized;
  return <>{box && <div className={`face-target ${tone}`} style={{ left: `${box.left * 100}%`, top: `${box.top * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }}><span className="scan-line" /></div>}<div className={`decision-panel ${tone}`}><div className="decision-icon">{tone === "verified" ? <Check weight="bold" /> : tone === "denied" ? <X weight="bold" /> : <IdentificationCard weight="duotone" />}</div><div className="decision-copy"><p className="eyebrow">{demoMode ? "DEMO SIGNAL" : "LIVE DECISION"}</p><h1>{title}</h1><p>{detail}</p></div>{result.distance != null && <div className="confidence"><strong>{Math.max(0, (1 - result.distance) * 100).toFixed(1)}%</strong><span>match</span></div>}</div></>;
}

function LiveGateway({ system, events, setEvents, openEnroll, notify }) {
  const videoRef = useRef(null), canvasRef = useRef(null), streamRef = useRef(null), scanTimer = useRef(null), demoTimer = useRef(null), scanInFlight = useRef(false), scanSession = useRef(0);
  const [cameraState, setCameraState] = useState("off"), [demoMode, setDemoMode] = useState(false), [result, setResult] = useState({ status: "OFFLINE" });
  const stopCamera = useCallback(() => { scanSession.current += 1; if (scanTimer.current) window.clearInterval(scanTimer.current); if (demoTimer.current) window.clearTimeout(demoTimer.current); scanTimer.current = null; demoTimer.current = null; streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; setDemoMode(false); setCameraState("off"); setResult({ status: "OFFLINE" }); }, []);
  const capture = useCallback(async (session) => {
    const video = videoRef.current, canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2 || !system.recognition || scanInFlight.current || scanSession.current !== session) return;
    scanInFlight.current = true;
    const context = canvas.getContext("2d"); canvas.width = 720; canvas.height = 405;
    const scale = Math.max(canvas.width / video.videoWidth, canvas.height / video.videoHeight), width = video.videoWidth * scale, height = video.videoHeight * scale;
    context.drawImage(video, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.78));
    try { if (!blob) throw new Error("The camera frame could not be captured."); const next = await api("/api/scan", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob }); if (scanSession.current !== session) return; setResult(next); if (["VERIFIED", "DENIED", "SPOOF_SUSPECTED"].includes(next.status) && next.event) setEvents((current) => [next.event, ...current.filter((item) => item.id !== next.event.id)].slice(0, 30)); }
    catch (error) { if (scanSession.current === session) { notify(error.message, "error"); stopCamera(); } }
    finally { scanInFlight.current = false; }
  }, [notify, setEvents, stopCamera, system.recognition]);
  const startCamera = useCallback(async () => {
    if (!system.recognition) return notify(system.backend ? "The recognition engine is unavailable. Check Settings for details." : "The local recognition service is offline. Demo mode is still available.", "error");
    stopCamera(); const session = scanSession.current; setCameraState("starting");
    try { const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false }); if (scanSession.current !== session) { stream.getTracks().forEach((track) => track.stop()); return; } streamRef.current = stream; videoRef.current.srcObject = stream; await videoRef.current.play(); if (scanSession.current !== session) return; setCameraState("live"); setResult({ status: "NO_FACE" }); scanTimer.current = window.setInterval(() => capture(session), 180); capture(session); }
    catch { if (scanSession.current === session) { setCameraState("off"); notify("Camera permission was not granted. Demo mode is still available.", "error"); } }
  }, [capture, notify, stopCamera, system.backend, system.recognition]);
  const runDemo = useCallback(() => { stopCamera(); const session = scanSession.current; setDemoMode(true); setCameraState("demo"); setResult({ status: "SCANNING", name: "Daniel Avery", distance: 0.032, box_normalized: { left: .34, top: .13, width: .32, height: .62 } }); demoTimer.current = window.setTimeout(() => { if (scanSession.current === session) setResult({ status: "VERIFIED", name: "Daniel Avery", distance: .013, box_normalized: { left: .34, top: .13, width: .32, height: .62 } }); }, 1700); }, [stopCamera]);
  useEffect(() => () => stopCamera(), [stopCamera]);
  const [title] = statusMeta(result.status);
  const cameraActive = cameraState === "live" || cameraState === "demo";
  return <section className="gateway-view"><div className="camera-stage"><video ref={videoRef} className={cameraState === "live" ? "camera-feed visible" : "camera-feed"} muted playsInline aria-label="Live gate camera" /><canvas ref={canvasRef} hidden />{!cameraActive && <div className="camera-empty"><CameraSlash weight="duotone" /><h2>{cameraState === "starting" ? "Starting gate camera…" : system.recognition ? "Gate camera is ready" : "Recognition service is offline"}</h2><p>{system.recognition ? "Use your device camera for live verification, or explore the complete flow safely in demo mode." : "Start the local Cereberus service for live verification, or explore the complete flow safely in demo mode."}</p><div className="empty-actions"><button className="primary-button" onClick={startCamera} disabled={cameraState === "starting" || !system.recognition}><Camera weight="fill" /> {cameraState === "starting" ? "Starting…" : "Start camera"}</button><button className="secondary-button" onClick={runDemo}><Play weight="fill" /> Demo mode</button></div></div>}{demoMode && <div className="demo-subject" aria-label="Demo camera visualization"><IdentificationCard weight="duotone" /></div>}{cameraActive && <ScanOverlay result={result} demoMode={demoMode} />}<div className="camera-label"><span className={cameraActive ? "status-pip" : "status-pip off"} /><div><strong>Lobby / North</strong><span>CAM 01 · {cameraState === "off" ? "Standby" : cameraState === "starting" ? "Starting" : cameraState === "demo" ? "Demo" : "Live"}</span></div></div>{cameraActive && <button className="pause-button" onClick={stopCamera} aria-label="Stop camera"><Pause weight="fill" /></button>}<div className="stage-side-panel"><p className="eyebrow">CURRENT STATE</p><h2>{title}</h2><div className="state-rule" /><div className="state-fact"><CheckCircle weight="duotone" /><span><strong>Identity match</strong><small>{result.name || "Waiting for subject"}</small></span></div><div className="state-fact"><ShieldCheck weight="duotone" /><span><strong>Live presence</strong><small>{result.status === "VERIFIED" ? "Confirmed" : "Blink challenge ready"}</small></span></div><div className="state-fact"><LockKeyOpen weight="duotone" /><span><strong>Gate relay</strong><small>{result.status === "VERIFIED" ? "Unlocked" : "Secured"}</small></span></div><button className="glass-action" onClick={openEnroll}><UserPlus /> Manage identities <ArrowRight /></button></div></div><EventTimeline events={events.slice(0, 4)} compact /></section>;
}

function EventTimeline({ events, compact = false }) {
  return <section className={compact ? "timeline compact" : "timeline"}><div className="section-heading"><div><p className="eyebrow">AUDIT TRAIL</p><h2>Recent activity</h2></div><span>{events.length} events</span></div><div className="event-list">{events.length === 0 && <div className="empty-row">No access events recorded yet.</div>}{events.map((event, index) => { const granted = ["GRANTED", "VERIFIED"].includes(event.status); return <article className="event-row" key={event.id || `${event.timestamp}-${index}`}><span className={granted ? "event-status granted" : "event-status denied"}>{granted ? <Check /> : <Warning />}</span><time>{formatTime(event.timestamp)}</time><div className="event-person"><strong>{event.name || "Unknown visitor"}</strong><span>{event.location || "Lobby / North"}</span></div><span className={granted ? "event-result granted" : "event-result denied"}>{granted ? "Access granted" : event.status === "SPOOF_SUSPECTED" ? "Spoof blocked" : "Access denied"}</span><span className="event-confidence">{event.distance != null ? `${Math.max(0, (1 - event.distance) * 100).toFixed(1)}% match` : "No match"}</span></article>; })}</div></section>;
}

function Identities({ users, onDelete, openEnroll }) {
  return <main className="content-page"><div className="page-title"><div><p className="eyebrow">ACCESS DIRECTORY</p><h1>Trusted identities</h1><p>People permitted to pass through monitored gates.</p></div><button className="primary-button" onClick={openEnroll}><UserPlus weight="fill" /> Enroll identity</button></div><div className="identity-list">{users.length === 0 ? <div className="page-empty"><IdentificationCard weight="duotone" /><h2>No identities enrolled</h2><p>Add a trusted person with five quick camera captures.</p></div> : users.map((user) => <article className="identity-row" key={user.name}><span className="identity-avatar">{user.name.slice(0, 2).toUpperCase()}</span><div><strong>{user.name}</strong><span>{user.samples} biometric samples</span></div><span className="identity-state"><span className="live-dot" /> Active</span><button className="icon-button danger" onClick={() => onDelete(user.name)} aria-label={`Remove ${user.name}`}><Trash /></button></article>)}</div></main>;
}

function Settings({ system }) {
  return <main className="content-page narrow"><div className="page-title"><div><p className="eyebrow">SYSTEM CONTROL</p><h1>Gate settings</h1><p>Runtime status and recognition safeguards.</p></div></div><div className="settings-list"><div className="setting-row"><span><strong>Recognition engine</strong><small>Face matching and landmark detection</small></span><span className={system.recognition ? "setting-value good" : "setting-value warning"}>{system.recognition ? "Available" : "Unavailable"}</span></div><div className="setting-row"><span><strong>Match threshold</strong><small>Lower values make identity matching stricter</small></span><span className="setting-value">{system.match_threshold ?? "0.50"}</span></div><div className="setting-row"><span><strong>Liveness challenge</strong><small>Blink verification protects against printed photos</small></span><span className="setting-value good">Enabled</span></div><div className="setting-row"><span><strong>Event retention</strong><small>Local audit logs and denied-entry snapshots</small></span><span className="setting-value">Local</span></div></div></main>;
}

function EnrollModal({ onClose, onComplete, notify }) {
  const videoRef = useRef(null), streamRef = useRef(null); const [name, setName] = useState(""), [samples, setSamples] = useState(0), [busy, setBusy] = useState(false);
  useEffect(() => { navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false }).then((stream) => { streamRef.current = stream; videoRef.current.srcObject = stream; return videoRef.current.play(); }).catch(() => notify("Camera access is required to enroll an identity.", "error")); return () => streamRef.current?.getTracks().forEach((track) => track.stop()); }, [notify]);
  async function captureSample() { if (!name.trim()) return notify("Enter the person’s name first.", "error"); const video = videoRef.current; if (!video?.videoWidth) return notify("The camera is not ready yet.", "error"); setBusy(true); const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 480; canvas.getContext("2d").drawImage(video, 0, 0, 640, 480); const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", .86)); try { const data = await api(`/api/enroll/sample?name=${encodeURIComponent(name.trim())}`, { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob }); setSamples(data.samples); if (data.complete) { notify(`${name.trim()} is now trusted.`, "success"); onComplete(); } } catch (error) { notify(error.message, "error"); } finally { setBusy(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="enroll-title"><div className="modal-head"><div><p className="eyebrow">NEW TRUSTED PERSON</p><h2 id="enroll-title">Enroll identity</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X /></button></div><div className="enroll-camera"><video ref={videoRef} muted playsInline /><div className="enroll-guide"><IdentificationCard weight="thin" /></div></div><label className="field-label">Full name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Daniel Avery" autoFocus maxLength={80} /></label><div className="sample-progress"><span>{Array.from({ length: 5 }).map((_, index) => <i key={index} className={index < samples ? "done" : ""} />)}</span><strong>{samples} / 5 samples</strong></div><p className="modal-note">Look straight ahead, then turn slightly between captures. Keep exactly one face in frame.</p><button className="primary-button full" onClick={captureSample} disabled={busy}>{busy ? "Analyzing…" : samples === 4 ? "Capture final sample" : "Capture sample"}</button></section></div>;
}

export function App() {
  const [active, setActive] = useState("gateway"), [events, setEvents] = useState([]), [users, setUsers] = useState([]), [system, setSystem] = useState({ backend: false, recognition: false }), [now, setNow] = useState(new Date()), [enrolling, setEnrolling] = useState(false), [toast, setToast] = useState(null), toastTimer = useRef(null);
  const notify = useCallback((message, tone = "success") => { if (toastTimer.current) window.clearTimeout(toastTimer.current); setToast({ message, tone }); toastTimer.current = window.setTimeout(() => setToast(null), 3600); }, []);
  const refresh = useCallback(async () => { try { const [health, log, directory] = await Promise.all([api("/api/health"), api("/api/events"), api("/api/users")]); setSystem({ ...health, backend: true }); setEvents(log.events); setUsers(directory.users); } catch { setSystem({ backend: false, recognition: false }); setEvents(fallbackEvents); } }, []);
  useEffect(() => { refresh(); const timer = window.setInterval(() => setNow(new Date()), 1000); return () => { window.clearInterval(timer); if (toastTimer.current) window.clearTimeout(toastTimer.current); }; }, [refresh]);
  async function removeUser(name) { if (!window.confirm(`Remove ${name} from trusted identities?`)) return; try { await api(`/api/users?name=${encodeURIComponent(name)}`, { method: "DELETE" }); notify(`${name} was removed.`); refresh(); } catch (error) { notify(error.message, "error"); } }
  const openEnroll = () => { setEnrolling(true); setActive("identities"); };
  return <div className="app-shell"><Header active={active} setActive={setActive} system={system} now={now} />{active === "gateway" && <LiveGateway system={system} events={events} setEvents={setEvents} openEnroll={openEnroll} notify={notify} />}{active === "identities" && <Identities users={users} onDelete={removeUser} openEnroll={() => setEnrolling(true)} />}{active === "activity" && <main className="content-page"><div className="page-title"><div><p className="eyebrow">SECURITY RECORD</p><h1>Event history</h1><p>Every gate decision, preserved locally for review.</p></div></div><EventTimeline events={events} /></main>}{active === "settings" && <Settings system={system} />}{enrolling && <EnrollModal onClose={() => setEnrolling(false)} onComplete={() => { setEnrolling(false); refresh(); }} notify={notify} />}{toast && <div className={`toast ${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"} aria-live="polite">{toast.tone === "error" ? <Warning weight="fill" /> : <CheckCircle weight="fill" />}{toast.message}</div>}</div>;
}
