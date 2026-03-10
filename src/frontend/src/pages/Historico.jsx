import { useState } from "react";
import "./historico.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

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
    <div className="hi-bar-track">
      <div className="hi-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function MachineCard({ machine }) {
  const st = getStatus(machine.status);
  const oc = oeeColor(machine.oee);
  return (
    <div className="hi-machine-card">
      <div className="hi-machine-status-bar" style={{ background: st.color }} />
      <div className="hi-machine-body">
        <div className="hi-machine-header">
          <span className="hi-machine-name">{machine.nome}</span>
          <span className="hi-machine-badge" style={{ color: st.color, background: st.bg }}>
            {st.label}
          </span>
        </div>

        <div className="hi-oee-block">
          <span className="hi-oee-label">OEE DO PERÍODO</span>
          <span className="hi-oee-value" style={{ color: oc }}>
            {machine.oee !== "-" && machine.oee !== null ? `${machine.oee}%` : "—"}
          </span>
        </div>

        <div className="hi-metrics">
          <div className="hi-metric-row">
            <span className="hi-metric-label">Disp.</span>
            <ProgressBar value={machine.disponibilidade} color={oeeColor(machine.disponibilidade)} />
            <span className="hi-metric-value" style={{ color: oeeColor(machine.disponibilidade) }}>
              {machine.disponibilidade}%
            </span>
          </div>
          <div className="hi-metric-row">
            <span className="hi-metric-label">Qual.</span>
            <ProgressBar value={machine.qualidade} color={oeeColor(machine.qualidade)} />
            <span className="hi-metric-value" style={{ color: oeeColor(machine.qualidade) }}>
              {machine.qualidade}%
            </span>
          </div>
          <div className="hi-metric-row">
            <span className="hi-metric-label">Perf.</span>
            <ProgressBar value={machine.performance} color={oeeColor(machine.performance)} />
            <span className="hi-metric-value" style={{ color: oeeColor(machine.performance) }}>
              {machine.performance}%
            </span>
          </div>
        </div>

        <div className="hi-prod-row">
          <span className="hi-prod-label">Prod.</span>
          <span className="hi-prod-value">
            <strong>{machine.produzido}</strong>
            <span className="hi-prod-meta"> / {machine.meta}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function LineSection({ linha }) {
  return (
    <div className="hi-line-section">
      <div className="hi-line-header">
        <span className="hi-line-badge">{linha.nome}</span>
        <span className="hi-line-meta">
          Produzido: <strong>{linha.realizado} un ({linha.realizado_pct}%)</strong>
          {" • "}
          Meta: <strong>{linha.meta_total} un</strong>
        </span>
      </div>
      <div className="hi-machine-grid">
        {linha.maquinas.map((m) => (
          <MachineCard key={m.id} machine={m} />
        ))}
      </div>
    </div>
  );
}

// Gera datetime-local string no fuso local
function toLocalDT(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const SHORTCUTS = [
  {
    label: "Hoje",
    range: () => {
      const s = new Date(); s.setHours(0,0,0,0);
      return [toLocalDT(s), toLocalDT(new Date())];
    },
  },
  {
    label: "Ontem",
    range: () => {
      const s = new Date(); s.setDate(s.getDate()-1); s.setHours(0,0,0,0);
      const e = new Date(); e.setDate(e.getDate()-1); e.setHours(23,59,0,0);
      return [toLocalDT(s), toLocalDT(e)];
    },
  },
  {
    label: "Últimas 8h",
    range: () => {
      const e = new Date();
      const s = new Date(e - 8*3600*1000);
      return [toLocalDT(s), toLocalDT(e)];
    },
  },
  {
    label: "Últimas 24h",
    range: () => {
      const e = new Date();
      const s = new Date(e - 24*3600*1000);
      return [toLocalDT(s), toLocalDT(e)];
    },
  },
  {
    label: "7 dias",
    range: () => {
      const e = new Date();
      const s = new Date(e - 7*24*3600*1000); s.setHours(0,0,0,0);
      return [toLocalDT(s), toLocalDT(e)];
    },
  },
];

export default function Historico() {
  const now = new Date();
  const startOfDay = new Date(now); startOfDay.setHours(0,0,0,0);

  const [inicio,    setInicio]    = useState(toLocalDT(startOfDay));
  const [fim,       setFim]       = useState(toLocalDT(now));
  const [data,      setData]      = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const [activeShortcut, setActiveShortcut] = useState("Hoje");

  function applyShortcut(s) {
    const [i, f] = s.range();
    setInicio(i);
    setFim(f);
    setActiveShortcut(s.label);
  }

  function buscar(customInicio, customFim) {
    const i = customInicio ?? inicio;
    const f = customFim    ?? fim;
    setLoading(true);
    setError(null);
    setData(null);
    fetch(`${API_BASE}/api/historico?data_inicio=${encodeURIComponent(i)}&data_fim=${encodeURIComponent(f)}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  return (
    <div className="hi-root">

      {/* ── Filtros ─────────────────────────────────────────── */}
      <div className="hi-filter-card">
        <div className="hi-filter-top">
          <div className="hi-filter-title-block">
            <h1 className="hi-page-title">Histórico de Produção</h1>
            <p className="hi-page-sub">Consulte métricas de qualquer período</p>
          </div>
          <div className="hi-filter-shortcuts">
            {SHORTCUTS.map((s) => (
              <button
                key={s.label}
                className={`hi-shortcut${activeShortcut === s.label ? " hi-shortcut--active" : ""}`}
                onClick={() => applyShortcut(s)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="hi-filter-row">
          <div className="hi-filter-field">
            <label className="hi-filter-label">Início</label>
            <input
              type="datetime-local"
              className="hi-filter-input"
              value={inicio}
              onChange={(e) => { setInicio(e.target.value); setActiveShortcut(null); }}
            />
          </div>
          <div className="hi-filter-sep">→</div>
          <div className="hi-filter-field">
            <label className="hi-filter-label">Fim</label>
            <input
              type="datetime-local"
              className="hi-filter-input"
              value={fim}
              onChange={(e) => { setFim(e.target.value); setActiveShortcut(null); }}
            />
          </div>
          <button
            className="hi-buscar-btn"
            onClick={() => buscar()}
            disabled={loading}
          >
            {loading ? "Buscando..." : "Buscar"}
          </button>
        </div>
      </div>

      {/* ── Estado ──────────────────────────────────────────── */}
      {error && <div className="hi-error">Erro: {error}</div>}

      {loading && (
        <div className="hi-loading">
          <div className="hi-spinner" />
          Buscando dados do período...
        </div>
      )}

      {/* ── Resultados ──────────────────────────────────────── */}
      {data && !loading && (
        <>
          {/* Banner do período */}
          <div className="hi-periodo-banner">
            <div className="hi-periodo-info">
              <span className="hi-periodo-label">Período consultado</span>
              <span className="hi-periodo-range">{data.periodo.inicio} → {data.periodo.fim}</span>
            </div>
            <div className="hi-periodo-oee">
              <span className="hi-periodo-oee-label">OEE Global do Período</span>
              <span
                className="hi-periodo-oee-val"
                style={{ color: oeeColor(data.oee_global) }}
              >
                {data.oee_global !== null ? `${data.oee_global}%` : "—"}
              </span>
            </div>
          </div>

          {/* Linhas */}
          <div className="hi-lines">
            {data.linhas.map((l) => <LineSection key={l.id} linha={l} />)}
          </div>
        </>
      )}

      {/* ── Empty state ─────────────────────────────────────── */}
      {!data && !loading && !error && (
        <div className="hi-empty">
          <div className="hi-empty-icon">📅</div>
          <div className="hi-empty-text">Selecione um período e clique em <strong>Buscar</strong></div>
        </div>
      )}

    </div>
  );
}
