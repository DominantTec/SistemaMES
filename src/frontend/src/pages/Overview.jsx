import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./overview.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE = API_BASE.replace(/^http/, "ws");

const STATUS_CONFIG = {
  produzindo:               { color: "#16a34a", bg: "#dcfce7", label: "Produzindo" },
  parada:                   { color: "#dc2626", bg: "#fee2e2", label: "Parada" },
  "aguardando manutentor":  { color: "#d97706", bg: "#fef3c7", label: "Ag. Manutentor" },
  "máquina em manutenção":  { color: "#7c3aed", bg: "#ede9fe", label: "Em Manutenção" },
  limpeza:                  { color: "#2563eb", bg: "#dbeafe", label: "Limpeza" },
  "passar padrão":          { color: "#0891b2", bg: "#cffafe", label: "Passar Padrão" },
  "alteração de parâmetros":{ color: "#9333ea", bg: "#f3e8ff", label: "Alt. Parâmetros" },
};

function getStatus(raw) {
  if (!raw) return { color: "#9ca3af", bg: "#f3f4f6", label: "-" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_CONFIG)) {
    if (key.includes(k)) return v;
  }
  return { color: "#9ca3af", bg: "#f3f4f6", label: raw };
}

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n)) return "#6b7280";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function ProgressBar({ value, color }) {
  const pct = Math.min(Math.max(Number(value) || 0, 0), 100);
  return (
    <div className="ov-bar-track">
      <div className="ov-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function MetricRow({ label, value, color }) {
  return (
    <div className="ov-metric-row">
      <span className="ov-metric-label">{label}</span>
      <ProgressBar value={value} color={color} />
      <span className="ov-metric-value" style={{ color }}>{value}%</span>
    </div>
  );
}

function MachineCard({ machine }) {
  const st = getStatus(machine.status);
  const oc = oeeColor(machine.oee);
  return (
    <div className="ov-machine-card">
      <div className="ov-machine-status-bar" style={{ background: st.color }} />
      <div className="ov-machine-body">
        <div className="ov-machine-header">
          <span className="ov-machine-name">{machine.nome}</span>
          <span className="ov-machine-status-badge" style={{ color: st.color, background: st.bg }}>
            {st.label}
          </span>
        </div>
        {machine.op && <span className="ov-machine-op">{machine.op}</span>}
        <div className="ov-oee-block">
          <span className="ov-oee-label">OEE ATUAL</span>
          <span className="ov-oee-value" style={{ color: oc }}>{machine.oee}%</span>
        </div>
        <div className="ov-metrics">
          <MetricRow label="Disp." value={machine.disponibilidade} color={oeeColor(machine.disponibilidade)} />
          <MetricRow label="Qual." value={machine.qualidade}       color={oeeColor(machine.qualidade)} />
        </div>
        <div className="ov-prod-row">
          <span className="ov-prod-label">Prod.</span>
          <span className="ov-prod-value">
            <strong style={{ color: "#16a34a" }}>{machine.produzido}</strong>
            <span className="ov-prod-sep"> / </span>
            <strong style={{ color: "#dc2626" }}>{machine.reprovado ?? 0}</strong>
            <span className="ov-prod-meta"> / {machine.meta}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function LineSection({ linha }) {
  return (
    <div className="ov-line-section">
      <div className="ov-line-header">
        <span className="ov-line-badge">{linha.nome}</span>
        <span className="ov-line-meta">
          Meta Hora: <strong>{linha.meta_hora} un</strong>
          {" • "}
          Realizado: <strong>{linha.realizado} un ({linha.realizado_pct}%)</strong>
        </span>
      </div>
      <div className="ov-machine-grid">
        {linha.maquinas.map((m) => (
          <Link key={m.id} to={`/maquina/${m.id}`} style={{ textDecoration: "none", color: "inherit" }}>
            <MachineCard machine={m} />
          </Link>
        ))}
      </div>
    </div>
  );
}

function EventTicker({ eventos }) {
  if (!eventos || eventos.length === 0) return null;
  return (
    <div className="ov-ticker">
      <span className="ov-ticker-label">ÚLTIMOS EVENTOS:</span>
      <div className="ov-ticker-items">
        {eventos.map((ev, i) => (
          <span key={i} className="ov-ticker-item">
            <span className="ov-ticker-time">{ev.hora}</span>
            <span className="ov-ticker-machine">{ev.maquina}</span>
            <span className="ov-ticker-desc">{ev.descricao}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function Overview() {
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);
  const wsRef             = useRef(null);
  const retryRef          = useRef(0);
  const retryTimerRef     = useRef(null);
  const aliveRef          = useRef(true);

  useEffect(() => {
    aliveRef.current = true;

    fetch(`${API_BASE}/api/overview`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));

    const connect = () => {
      if (!aliveRef.current) return;
      const ws = new WebSocket(`${WS_BASE}/api/overview/ws`);
      wsRef.current = ws;
      ws.onopen  = () => { retryRef.current = 0; };
      ws.onmessage = (ev) => { try { setData(JSON.parse(ev.data)); } catch {} };
      ws.onclose = () => {
        if (!aliveRef.current) return;
        retryRef.current += 1;
        const delay = Math.min(1000 * 2 ** (retryRef.current - 1), 10000);
        retryTimerRef.current = setTimeout(connect, delay);
      };
    };
    connect();

    return () => {
      aliveRef.current = false;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  if (error) return <div className="ov-error">Erro ao carregar: {error}</div>;
  if (!data) return <div className="ov-loading"><div className="ov-spinner" />Carregando...</div>;

  const { topbar, linhas } = data;

  return (
    <div className="ov-root">
      {/* ── Topbar ─────────────────────────────────────────── */}
      <header className="ov-topbar">
        <div className="ov-topbar-left">
          <h1 className="ov-topbar-title">{topbar.titulo}</h1>
          <div className="ov-topbar-kpis">
            <span className="ov-kpi-dot" />
            <span className="ov-kpi">
              <span className="ov-kpi-label">OEE Global:</span>
              <strong style={{ color: oeeColor(topbar.oee_global) }}>{topbar.oee_global}%</strong>
            </span>
            <span className="ov-kpi-sep">•</span>
            <span className="ov-kpi">
              <span className="ov-kpi-label">Máquinas Ativas:</span>
              <strong>{topbar.maquinas_ativas}/{topbar.maquinas_total}</strong>
            </span>
          </div>
        </div>
        <div className="ov-topbar-right">
          <div className="ov-topbar-pill">{topbar.data_hora}</div>
          <div className="ov-topbar-avatar">{topbar.user_initials}</div>
        </div>
      </header>

      {/* ── Ticker ─────────────────────────────────────────── */}
      <EventTicker eventos={topbar.eventos_recentes} />

      {/* ── Linhas ─────────────────────────────────────────── */}
      <div className="ov-lines">
        {linhas.map((l) => <LineSection key={l.id} linha={l} />)}
      </div>
    </div>
  );
}