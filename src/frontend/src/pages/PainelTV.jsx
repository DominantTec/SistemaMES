import { useEffect, useRef, useState } from "react";
import "./paineltv.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE    = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE     = API_BASE.replace(/^http/, "ws");

/* ── Status config ───────────────────────────────────────── */
const STATUS_CONFIG = {
  produzindo:                { color: "#22c55e", bg: "rgba(34,197,94,0.12)",   label: "PRODUZINDO" },
  parada:                    { color: "#ef4444", bg: "rgba(239,68,68,0.12)",   label: "PARADA" },
  "aguardando manutentor":   { color: "#f59e0b", bg: "rgba(245,158,11,0.12)", label: "AG. MANUTENTOR" },
  "máquina em manutenção":   { color: "#a78bfa", bg: "rgba(167,139,250,0.12)","label": "MANUTENÇÃO" },
  limpeza:                   { color: "#38bdf8", bg: "rgba(56,189,248,0.12)",  label: "LIMPEZA" },
  "passar padrão":           { color: "#34d399", bg: "rgba(52,211,153,0.12)", label: "PASSAR PADRÃO" },
  "alteração de parâmetros": { color: "#fb923c", bg: "rgba(251,146,60,0.12)", label: "ALT. PARÂMETROS" },
};

function getStatus(raw) {
  if (!raw) return { color: "#4b5563", bg: "transparent", label: "—" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_CONFIG)) {
    if (key.includes(k)) return v;
  }
  return { color: "#6b7280", bg: "transparent", label: String(raw).toUpperCase() };
}

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n)) return "#6b7280";
  if (n >= 75)  return "#22c55e";
  if (n >= 50)  return "#f59e0b";
  return "#ef4444";
}

function metricClass(val) {
  const n = Number(val);
  if (isNaN(n)) return "neutral";
  if (n >= 90)  return "green";
  if (n >= 70)  return "yellow";
  return "red";
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined || v === "-") return "—";
  const n = Number(v);
  return isNaN(n) ? String(v) : `${n}${suffix}`;
}

/* ── Relógio ─────────────────────────────────────────────── */
function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="tv-clock">
      <span className="tv-clock-time">
        {now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
      <span className="tv-clock-date">
        {now.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}
      </span>
    </div>
  );
}

/* ── Linha da tabela (máquina) ───────────────────────────── */
function MaquinaRow({ machine, metaHora, isWorst }) {
  const st       = getStatus(machine.status);
  const isOk     = machine.status?.toLowerCase().includes("produzindo");
  const isStopped = !isOk && machine.status && machine.status !== "-";

  const pct = machine.meta > 0
    ? Math.min(100, Math.round(100 * (machine.produzido ?? 0) / machine.meta))
    : 0;

  const pcHora = typeof machine.meta === "number" && typeof machine.performance === "number"
    ? Math.round((metaHora / 8) * (machine.performance / 100 - 1))
    : null;

  const mClass = (field) => isStopped ? "neutral" : metricClass(machine[field]);

  return (
    <tr className={`tv-row${isStopped ? " tv-row--stopped" : isWorst ? " tv-row--alert" : ""}`}>
      <td className="tv-td tv-td--name">{machine.nome}</td>

      <td className={`tv-td tv-td--metric tv-cell--${mClass("performance")}`}>
        {fmt(machine.performance, "%")}
      </td>
      <td className={`tv-td tv-td--metric tv-cell--${mClass("disponibilidade")}`}>
        {fmt(machine.disponibilidade, "%")}
      </td>
      <td className={`tv-td tv-td--metric tv-cell--${mClass("qualidade")}`}>
        {fmt(machine.qualidade, "%")}
      </td>
      <td className={`tv-td tv-td--metric tv-cell--${mClass("oee")}`}>
        {fmt(machine.oee, "%")}
      </td>

      {/* Produzido / Meta com barra */}
      <td className="tv-td tv-td--prod">
        <div className="tv-prod-row">
          <span className="tv-prod-val">{machine.produzido ?? "—"}</span>
          <span className="tv-prod-sep">/</span>
          <span className="tv-prod-meta">{machine.meta ?? "—"}</span>
        </div>
        {machine.meta > 0 && (
          <div className="tv-prod-track">
            <div
              className="tv-prod-fill"
              style={{
                width: `${pct}%`,
                background: pct >= 80 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444",
              }}
            />
          </div>
        )}
        <span className="tv-prod-pct">{pct}%</span>
      </td>

      {/* Pç/Hora delta */}
      <td className="tv-td tv-td--metric">
        <span className={`tv-delta tv-delta--${pcHora === null ? "neutral" : pcHora >= 0 ? "green" : "red"}`}>
          {pcHora !== null ? (pcHora >= 0 ? `+${pcHora}` : pcHora) : "—"}
        </span>
      </td>

      <td className="tv-td tv-td--status">
        <span className="tv-status-badge" style={{ color: st.color, background: st.bg }}>
          {st.label}
        </span>
      </td>
    </tr>
  );
}

/* ── Painel de turnos ────────────────────────────────────── */
function TurnPanel({ linha, turnoAtual }) {
  const totalMeta = linha?.maquinas?.reduce(
    (s, m) => s + (typeof m.meta === "number" ? m.meta : 0), 0) ?? 0;
  const totalProd = linha?.maquinas?.reduce(
    (s, m) => s + (typeof m.produzido === "number" ? m.produzido : 0), 0) ?? 0;
  const progresso = totalMeta > 0 ? Math.min(100, Math.round(totalProd / totalMeta * 100)) : 0;
  const barColor  = progresso >= 90 ? "#22c55e" : progresso >= 70 ? "#f59e0b" : "#ef4444";

  return (
    <div className="tv-turns">
      <div className="tv-turns-label">Turnos</div>
      <div className="tv-turns-grid">

        <div className="tv-turn-col">
          <div className="tv-turn-head">
            1º Turno{turnoAtual?.nome && turnoAtual.nome !== "-" ? ` — ${turnoAtual.nome}` : ""}
          </div>
          <div className="tv-turn-rows">
            <div className="tv-turn-item">
              <span className="tv-turn-item-label">Programado</span>
              <span className="tv-turn-item-val">{totalMeta}</span>
            </div>
            <div className="tv-turn-item">
              <span className="tv-turn-item-label">Produzido</span>
              <div className="tv-turn-bar-wrap">
                <div className="tv-turn-track">
                  <div className="tv-turn-fill" style={{ width: `${progresso}%`, background: barColor }} />
                  <span className="tv-turn-fill-label">{totalProd}</span>
                </div>
              </div>
            </div>
            <div className="tv-turn-item">
              <span className="tv-turn-item-label">Resultado</span>
              <span className="tv-turn-item-val" style={{ color: barColor }}>
                {progresso}%
              </span>
            </div>
          </div>
        </div>

        {[2, 3].map((n) => (
          <div key={n} className="tv-turn-col tv-turn-col--dim">
            <div className="tv-turn-head">{n}º Turno</div>
            <div className="tv-turn-rows">
              {["Programado", "Produzido", "Resultado"].map((l) => (
                <div key={l} className="tv-turn-item">
                  <span className="tv-turn-item-label">{l}</span>
                  <span className="tv-turn-item-val tv-turn-item-val--dim">—</span>
                </div>
              ))}
            </div>
          </div>
        ))}

      </div>
    </div>
  );
}

/* ── Seção de linha ──────────────────────────────────────── */
function LineSection({ linha, turno }) {
  const maquinas   = linha.maquinas ?? [];
  const oees       = maquinas.map((m) => (typeof m.oee === "number" ? m.oee : 999));
  const validOees  = oees.filter((v) => v < 999);
  const oeeMedia   = validOees.length
    ? Math.round(validOees.reduce((a, b) => a + b, 0) / validOees.length)
    : null;
  const worstIdx   = oees.indexOf(Math.min(...oees));
  const metaHora   = Math.round((linha.meta_hora ?? 0) / Math.max(maquinas.length, 1));

  const totalMeta = maquinas.reduce((s, m) => s + (typeof m.meta === "number" ? m.meta : 0), 0);
  const totalProd = maquinas.reduce((s, m) => s + (typeof m.produzido === "number" ? m.produzido : 0), 0);
  const pct       = totalMeta > 0 ? Math.min(100, Math.round(totalProd / totalMeta * 100)) : 0;

  return (
    <section className="tv-section">
      <div className="tv-section-header">
        <span className="tv-section-name">{linha.nome}</span>
        <div className="tv-section-stats">
          {oeeMedia !== null && (
            <span className="tv-stat">
              OEE <strong style={{ color: oeeColor(oeeMedia) }}>{oeeMedia}%</strong>
            </span>
          )}
          <span className="tv-stat-sep" />
          <span className="tv-stat">
            {totalProd} / {totalMeta} un
          </span>
          <span className="tv-stat-sep" />
          <span className="tv-stat">
            Meta <strong style={{ color: oeeColor(pct) }}>{pct}%</strong>
          </span>
          <span className="tv-stat-sep" />
          <span className="tv-stat">{maquinas.length} máq.</span>
        </div>
      </div>

      <div className="tv-table-wrap">
        <table className="tv-table">
          <thead>
            <tr>
              <th className="tv-th tv-th--name">Máquina</th>
              <th className="tv-th">Eficiência</th>
              <th className="tv-th">Disponib.</th>
              <th className="tv-th">Qualidade</th>
              <th className="tv-th">OEE</th>
              <th className="tv-th">Produção</th>
              <th className="tv-th">Pç/Hora</th>
              <th className="tv-th">Estado</th>
            </tr>
          </thead>
          <tbody>
            {maquinas.length > 0 ? (
              maquinas.map((m, i) => (
                <MaquinaRow
                  key={m.id}
                  machine={m}
                  metaHora={metaHora}
                  isWorst={i === worstIdx && oees[i] < 999}
                />
              ))
            ) : (
              <tr>
                <td colSpan={8} className="tv-empty">Nenhuma máquina nesta linha.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <TurnPanel linha={linha} turnoAtual={turno} />
    </section>
  );
}

/* ── Componente principal ────────────────────────────────── */
export default function PainelTV() {
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
        retryTimer.current = setTimeout(
          connect,
          Math.min(1000 * 2 ** (retryRef.current - 1), 10000)
        );
      };
    };
    connect();

    return () => {
      aliveRef.current = false;
      clearTimeout(retryTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  if (error) return <div className="tv-error">Erro: {error}</div>;
  if (!data)  return (
    <div className="tv-loading">
      <div className="tv-spinner" />
      Carregando...
    </div>
  );

  const { topbar, linhas, turno_atual } = data;

  return (
    <div className="tv-root">

      {/* ── Topbar ─────────────────────────────────────────── */}
      <header className="tv-topbar">
        <div className="tv-topbar-left">
          <span className="tv-factory-name">Chão de Fábrica</span>
          <div className="tv-kpis">
            <div className="tv-kpi">
              <span className="tv-kpi-label">OEE Global</span>
              <span className="tv-kpi-val" style={{ color: oeeColor(topbar.oee_global) }}>
                {topbar.oee_global}%
              </span>
            </div>
            <div className="tv-kpi-sep" />
            <div className="tv-kpi">
              <span className="tv-kpi-label">Máquinas Ativas</span>
              <span className="tv-kpi-val">
                {topbar.maquinas_ativas}
                <span className="tv-kpi-total">/{topbar.maquinas_total}</span>
              </span>
            </div>
            {turno_atual?.nome && turno_atual.nome !== "-" && (
              <>
                <div className="tv-kpi-sep" />
                <div className="tv-kpi">
                  <span className="tv-kpi-label">Turno</span>
                  <span className="tv-kpi-val">{turno_atual.nome}</span>
                </div>
                <div className="tv-kpi">
                  <span className="tv-kpi-label">Encerra em</span>
                  <span className="tv-kpi-val tv-kpi-val--warn">{turno_atual.encerra_em}</span>
                </div>
              </>
            )}
          </div>
        </div>
        <Clock />
      </header>

      {/* ── Linhas ─────────────────────────────────────────── */}
      <main className="tv-content">
        {linhas.map((l) => (
          <LineSection key={l.id} linha={l} turno={turno_atual} />
        ))}
      </main>

    </div>
  );
}
