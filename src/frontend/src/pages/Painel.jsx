import { useEffect, useRef, useState } from "react";
import "./painel.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE  = API_BASE.replace(/^http/, "ws");

const STATUS_CONFIG = {
  produzindo:                { color: "#22c55e", bg: "#052e16", label: "PRODUZINDO" },
  parada:                    { color: "#ef4444", bg: "#2d0a0a", label: "PARADA" },
  "aguardando manutentor":   { color: "#f59e0b", bg: "#2d1a00", label: "AG. MANUTENTOR" },
  "máquina em manutenção":   { color: "#a78bfa", bg: "#1e0d3d", label: "MANUTENÇÃO" },
  limpeza:                   { color: "#38bdf8", bg: "#082032", label: "LIMPEZA" },
  "passar padrão":           { color: "#34d399", bg: "#052e1c", label: "PASSAR PADRÃO" },
  "alteração de parâmetros": { color: "#fb923c", bg: "#2d1200", label: "ALT. PARÂMETROS" },
};

function getStatus(raw) {
  if (!raw) return { color: "#6b7280", bg: "#1a1a1a", label: "-" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_CONFIG)) {
    if (key.includes(k)) return v;
  }
  return { color: "#6b7280", bg: "#1a1a1a", label: String(raw).toUpperCase() };
}

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n)) return "#6b7280";
  if (n >= 75) return "#22c55e";
  if (n >= 50) return "#f59e0b";
  return "#ef4444";
}

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="pn-clock">
      <span className="pn-clock-time">
        {now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
      <span className="pn-clock-date">
        {now.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}
      </span>
    </div>
  );
}

function MachineCard({ machine }) {
  const st  = getStatus(machine.status);
  const oc  = oeeColor(machine.oee);
  const pct = machine.meta > 0
    ? Math.min(100, Math.round(100 * machine.produzido / machine.meta))
    : 0;

  return (
    <div className="pn-card" style={{ borderColor: st.color }}>
      <div className="pn-card-bar" style={{ background: st.color }} />

      <div className="pn-card-body">
        {/* Nome + status */}
        <div className="pn-card-top">
          <span className="pn-card-name">{machine.nome}</span>
          <span className="pn-card-badge" style={{ color: st.color, background: st.bg }}>
            {st.label}
          </span>
        </div>

        {/* OEE grande */}
        <div className="pn-card-oee" style={{ color: oc }}>
          {machine.oee !== "-" ? `${machine.oee}%` : "—"}
          <span className="pn-card-oee-label">OEE</span>
        </div>

        {/* Barra de produção */}
        <div className="pn-prod-block">
          <div className="pn-prod-nums">
            <span className="pn-prod-value">{machine.produzido}</span>
            <span className="pn-prod-sep">/</span>
            <span className="pn-prod-meta">{machine.meta}</span>
            <span className="pn-prod-unit">un</span>
          </div>
          <div className="pn-prod-track">
            <div
              className="pn-prod-fill"
              style={{ width: `${pct}%`, background: pct >= 80 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444" }}
            />
          </div>
          <span className="pn-prod-pct">{pct}% da meta</span>
        </div>

        {/* Operador */}
        {machine.op && (
          <div className="pn-card-operador">
            <span className="pn-op-ico">👤</span>
            <span className="pn-op-nome">{machine.op}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function LineBlock({ linha }) {
  return (
    <div className="pn-line">
      <div className="pn-line-header">
        <span className="pn-line-name">{linha.nome}</span>
        <span className="pn-line-stats">
          {linha.realizado} un produzidas &nbsp;·&nbsp; {linha.realizado_pct}% da meta
        </span>
      </div>
      <div className="pn-machine-grid">
        {linha.maquinas.map((m) => (
          <MachineCard key={m.id} machine={m} />
        ))}
      </div>
    </div>
  );
}

export default function Painel() {
  const [data,  setData]  = useState(null);
  const [error, setError] = useState(null);
  const wsRef      = useRef(null);
  const retryRef   = useRef(0);
  const retryTimer = useRef(null);
  const aliveRef   = useRef(true);

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
      ws.onopen    = () => { retryRef.current = 0; };
      ws.onmessage = (ev) => { try { setData(JSON.parse(ev.data)); } catch {} };
      ws.onclose   = () => {
        if (!aliveRef.current) return;
        retryRef.current += 1;
        retryTimer.current = setTimeout(connect, Math.min(1000 * 2 ** (retryRef.current - 1), 10000));
      };
    };
    connect();

    return () => {
      aliveRef.current = false;
      clearTimeout(retryTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  if (error) return <div className="pn-error">Erro: {error}</div>;
  if (!data)  return <div className="pn-loading"><div className="pn-spinner" />Carregando...</div>;

  const { topbar, linhas, turno_atual } = data;

  return (
    <div className="pn-root">

      {/* ── Topbar ─────────────────────────────────────────── */}
      <header className="pn-topbar">
        <div className="pn-topbar-left">
          <span className="pn-factory-name">Chão de Fábrica</span>
          <div className="pn-kpis">
            <div className="pn-kpi">
              <span className="pn-kpi-label">OEE Global</span>
              <span className="pn-kpi-val" style={{ color: oeeColor(topbar.oee_global) }}>
                {topbar.oee_global}%
              </span>
            </div>
            <div className="pn-kpi-sep" />
            <div className="pn-kpi">
              <span className="pn-kpi-label">Máquinas Ativas</span>
              <span className="pn-kpi-val">
                {topbar.maquinas_ativas}
                <span className="pn-kpi-total">/{topbar.maquinas_total}</span>
              </span>
            </div>
            {turno_atual?.nome && turno_atual.nome !== "-" && (
              <>
                <div className="pn-kpi-sep" />
                <div className="pn-kpi">
                  <span className="pn-kpi-label">Turno</span>
                  <span className="pn-kpi-val">{turno_atual.nome}</span>
                </div>
                <div className="pn-kpi">
                  <span className="pn-kpi-label">Encerra em</span>
                  <span className="pn-kpi-val pn-kpi-val--warn">{turno_atual.encerra_em}</span>
                </div>
              </>
            )}
          </div>
        </div>
        <Clock />
      </header>

      {/* ── Linhas ─────────────────────────────────────────── */}
      <main className="pn-content">
        {linhas.map((l) => <LineBlock key={l.id} linha={l} />)}
      </main>

    </div>
  );
}
