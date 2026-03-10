import { useEffect, useRef, useState } from "react";
import "./painelmes.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE    = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE     = API_BASE.replace(/^http/, "ws");

/* ── Helpers de cor ──────────────────────────────────────── */
function pctColor(val) {
  const n = Number(val);
  if (isNaN(n)) return "neutral";
  if (n >= 90)  return "green";
  if (n >= 70)  return "yellow";
  return "red";
}

function deltaColor(val) {
  const n = Number(val);
  if (isNaN(n)) return "neutral";
  return n >= 0 ? "green" : "red";
}

function pctDot(val) {
  return <span className={`mes-dot mes-dot--${pctColor(val)}`} />;
}

function deltaDot(val) {
  return <span className={`mes-dot mes-dot--${deltaColor(val)}`} />;
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined || v === "-") return "—";
  const n = Number(v);
  return isNaN(n) ? String(v) : `${n}${suffix}`;
}

/* ── Linha da máquina ────────────────────────────────────── */
function MaquinaRow({ machine, metaHora, isWorst }) {
  const acumulado  = typeof machine.produzido === "number" ? machine.produzido : null;

  // Pç/Hora: estimativa — meta/hora * (performance/100 - 1) → delta vs expected rate
  const pcHora = typeof machine.meta === "number" && typeof machine.performance === "number"
    ? Math.round((metaHora / 8) * (machine.performance / 100 - 1))
    : null;

  const statusLabel = machine.status && machine.status !== "-"
    ? machine.status.charAt(0).toUpperCase() + machine.status.slice(1).toLowerCase()
    : "—";

  const isOk = machine.status && machine.status.toLowerCase().includes("produzindo");
  const isStopped = !isOk && machine.status && machine.status !== "-";

  return (
    <tr className={`mes-row${isStopped ? " mes-row--stopped" : isWorst ? " mes-row--alert" : ""}`}>
      <td className="mes-td mes-td--name">{machine.nome}</td>

      <td className="mes-td mes-td--metric">
        {pctDot(machine.performance)}
        <span className={`mes-val mes-val--${pctColor(machine.performance)}`}>
          {fmt(machine.performance, "%")}
        </span>
      </td>

      <td className="mes-td mes-td--metric">
        {pctDot(machine.disponibilidade)}
        <span className={`mes-val mes-val--${pctColor(machine.disponibilidade)}`}>
          {fmt(machine.disponibilidade, "%")}
        </span>
      </td>

      <td className="mes-td mes-td--metric">
        {pctDot(machine.qualidade)}
        <span className={`mes-val mes-val--${pctColor(machine.qualidade)}`}>
          {fmt(machine.qualidade, "%")}
        </span>
      </td>

      <td className="mes-td mes-td--metric">
        {pctDot(machine.oee)}
        <span className={`mes-val mes-val--${pctColor(machine.oee)}`}>
          {fmt(machine.oee, "%")}
        </span>
      </td>

      <td className="mes-td mes-td--metric">
        {deltaDot(pcHora)}
        <span className={`mes-val mes-val--${deltaColor(pcHora)}`}>
          {pcHora !== null ? (pcHora >= 0 ? `+${pcHora}` : pcHora) : "—"}
        </span>
      </td>

      <td className="mes-td mes-td--metric">
        <span className="mes-val mes-val--neutral">
          {acumulado !== null ? acumulado : "—"}
        </span>
      </td>

      <td className="mes-td mes-td--status">
        <span className={`mes-status-badge mes-status-badge--${isOk ? "ok" : "stop"}`}>
          {isOk ? "Ok" : statusLabel}
        </span>
      </td>
    </tr>
  );
}

/* ── Painel de turnos ────────────────────────────────────── */
function TurnPanel({ linha, turnoAtual }) {
  const totalMeta      = linha?.maquinas?.reduce((s, m) => s + (typeof m.meta === "number" ? m.meta : 0), 0) ?? 0;
  const totalProduzido = linha?.maquinas?.reduce((s, m) => s + (typeof m.produzido === "number" ? m.produzido : 0), 0) ?? 0;
  const progresso      = totalMeta > 0 ? Math.min(100, Math.round(totalProduzido / totalMeta * 100)) : 0;

  const rows = [
    { label: "Programado", v1: totalMeta,      v2: 0, v3: 0, hasBar: false },
    { label: "Produzido",  v1: totalProduzido, v2: 0, v3: 0, hasBar: true,  pct: progresso },
    { label: "Resultado",  v1: totalProduzido, v2: 0, v3: 0, hasBar: false },
  ];

  return (
    <div className="mes-turn-panel">
      <table className="mes-turn-table">
        <thead>
          <tr>
            <th className="mes-turn-th mes-turn-th--label" />
            <th className="mes-turn-th">1º Turno{turnoAtual?.nome ? ` — ${turnoAtual.nome}` : ""}</th>
            <th className="mes-turn-th">2º Turno</th>
            <th className="mes-turn-th">3º Turno</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="mes-turn-row">
              <td className="mes-turn-td mes-turn-td--label">{r.label}</td>
              <td className="mes-turn-td">
                {r.hasBar ? (
                  <div className="mes-prog-wrap">
                    <div className="mes-prog-track">
                      <div className="mes-prog-fill" style={{ width: `${r.pct}%` }} />
                      <span className="mes-prog-label">{r.v1}</span>
                    </div>
                  </div>
                ) : (
                  <span>{r.v1}</span>
                )}
              </td>
              <td className="mes-turn-td mes-turn-td--empty">{r.v2 || "—"}</td>
              <td className="mes-turn-td mes-turn-td--empty">{r.v3 || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Componente principal ────────────────────────────────── */
export default function PainelMES() {
  const [data,        setData]        = useState(null);
  const [lineIndex,   setLineIndex]   = useState(0);
  const [error,       setError]       = useState(null);
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

  if (error) return <div className="mes-error">Erro: {error}</div>;
  if (!data)  return <div className="mes-loading"><div className="mes-spinner" />Carregando...</div>;

  const linhas     = data.linhas ?? [];
  const totalLines = linhas.length;
  const linha      = linhas[lineIndex] ?? null;
  const turno      = data.turno_atual;

  const safeIdx = (d) => {
    setLineIndex((i) => Math.min(Math.max(i + d, 0), totalLines - 1));
  };

  // Pior máquina = menor OEE (para highlight)
  const maquinas   = linha?.maquinas ?? [];
  const oees       = maquinas.map((m) => typeof m.oee === "number" ? m.oee : 999);
  const worstIdx   = oees.indexOf(Math.min(...oees));
  const metaHora   = linha ? Math.round((linha.meta_hora ?? 0) / Math.max(maquinas.length, 1)) : 0;

  return (
    <div className="mes-root">

      {/* ── Sidebar vertical ─────────────────────────────── */}
      <div className="mes-sidebar">
        <span className="mes-sidebar-label">{linha?.nome ?? "—"}</span>
      </div>

      {/* ── Conteúdo principal ───────────────────────────── */}
      <div className="mes-content">

        {/* Navegação de linha */}
        <div className="mes-nav">
          <button
            className="mes-nav-btn"
            onClick={() => safeIdx(-1)}
            disabled={lineIndex === 0}
          >←</button>
          <span className="mes-nav-num">{lineIndex + 1}</span>
          <button
            className="mes-nav-btn"
            onClick={() => safeIdx(1)}
            disabled={lineIndex >= totalLines - 1}
          >→</button>
          <span className="mes-nav-title">{linha?.nome}</span>
          <span className="mes-nav-meta">
            {maquinas.length} máquinas &nbsp;·&nbsp; OEE médio:{" "}
            <strong>
              {maquinas.length
                ? Math.round(oees.filter((v) => v < 999).reduce((a, b) => a + b, 0) / maquinas.length) + "%"
                : "—"}
            </strong>
          </span>
        </div>

        {/* Tabela de máquinas */}
        <div className="mes-table-wrap">
          <table className="mes-table">
            <thead>
              <tr>
                <th className="mes-th mes-th--name">Máquina</th>
                <th className="mes-th">Eficiência</th>
                <th className="mes-th">Disponibilid.</th>
                <th className="mes-th">Qualidade</th>
                <th className="mes-th">OEE</th>
                <th className="mes-th">Pç/Hora</th>
                <th className="mes-th">Acumulado</th>
                <th className="mes-th">Estado</th>
              </tr>
            </thead>
            <tbody>
              {maquinas.length > 0 ? maquinas.map((m, i) => (
                <MaquinaRow
                  key={m.id}
                  machine={m}
                  metaHora={metaHora}
                  isWorst={i === worstIdx && oees[i] < 999}
                />
              )) : (
                <tr>
                  <td colSpan={8} className="mes-empty">Nenhuma máquina nesta linha.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Painel de turnos */}
        <TurnPanel linha={linha} turnoAtual={turno} />

      </div>
    </div>
  );
}
