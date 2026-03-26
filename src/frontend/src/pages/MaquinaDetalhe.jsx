import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import "./MaquinaDetalhe.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE  = API_BASE.replace(/^http/, "ws");

const STATUS_MAP = {
  produzindo:               { label: "EM OPERAÇÃO",    color: "#16a34a", bg: "#dcfce7" },
  parada:                   { label: "PARADA",         color: "#dc2626", bg: "#fee2e2" },
  "aguardando manutentor":  { label: "AG. MANUTENTOR", color: "#d97706", bg: "#fef3c7" },
  "máquina em manutenção":  { label: "EM MANUTENÇÃO",  color: "#7c3aed", bg: "#ede9fe" },
  limpeza:                  { label: "LIMPEZA",        color: "#2563eb", bg: "#dbeafe" },
  "passar padrão":          { label: "PASSAR PADRÃO",  color: "#0891b2", bg: "#cffafe" },
};

function getStatus(raw) {
  if (!raw) return { label: "-", color: "#6b7280", bg: "#f3f4f6" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_MAP)) {
    if (key.includes(k)) return v;
  }
  return { label: raw, color: "#6b7280", bg: "#f3f4f6" };
}

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n) || val === null) return "#6b7280";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined || v === "-") return "-";
  return `${v}${suffix}`;
}

function KpiCard({ label, value, suffix = "%", sub, color }) {
  const c = color || oeeColor(value);
  return (
    <div className="md-kpi-card">
      <div className="md-kpi-label">{label}</div>
      <div className="md-kpi-value" style={{ color: c }}>{fmt(value, suffix)}</div>
      {sub && <div className="md-kpi-sub">{sub}</div>}
    </div>
  );
}

function MtbfRow({ label, value }) {
  return (
    <div className="md-mtbf-row">
      <span className="md-mtbf-label">{label}</span>
      <span className="md-mtbf-value">{value || "-"}</span>
    </div>
  );
}

function parseHM(str) {
  if (!str || str === "-") return 0;
  const m = str.match(/(\d+)h\s*(\d+)m/);
  return m ? parseInt(m[1]) * 3600 + parseInt(m[2]) * 60 : 0;
}

function DonutChart({ mtbf, mttr }) {
  const vMtbf = parseHM(mtbf);
  const vMttr = parseHM(mttr);
  const total  = vMtbf + vMttr;

  if (total === 0) return (
    <div className="md-donut-empty">Sem dados suficientes para o gráfico</div>
  );

  const SIZE  = 150;
  const THICK = 28;
  const r     = (SIZE - THICK) / 2;
  const circ  = 2 * Math.PI * r;

  const pctMtbf = vMtbf / total;
  const pctMttr = vMttr / total;

  const segments = [
    { pct: pctMtbf, color: "#16a34a", label: "MTBF", value: mtbf },
    { pct: pctMttr, color: "#dc2626", label: "MTTR", value: mttr },
  ];

  let cumAngle = -90;
  return (
    <div className="md-donut-wrap">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {segments.map((seg, i) => {
          const dash   = seg.pct * circ;
          const gap    = circ - dash;
          const rotate = cumAngle;
          cumAngle += seg.pct * 360;
          return (
            <circle
              key={i}
              cx={SIZE / 2} cy={SIZE / 2} r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={THICK}
              strokeDasharray={`${dash} ${gap}`}
              strokeLinecap="butt"
              transform={`rotate(${rotate} ${SIZE / 2} ${SIZE / 2})`}
            />
          );
        })}
        <text x={SIZE / 2} y={SIZE / 2 - 6}  textAnchor="middle" className="md-donut-pct" fill="#111827">
          {Math.round(pctMtbf * 100)}%
        </text>
        <text x={SIZE / 2} y={SIZE / 2 + 12} textAnchor="middle" className="md-donut-sub" fill="#6b7280">
          operando
        </text>
      </svg>

      <div className="md-donut-legend">
        {segments.map((seg) => (
          <div key={seg.label} className="md-donut-legend-item">
            <span className="md-donut-legend-dot" style={{ background: seg.color }} />
            <span className="md-donut-legend-label">{seg.label}</span>
            <span className="md-donut-legend-val">{seg.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MaquinaDetalhe() {
  const { machineId } = useParams();
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);
  const wsRef             = useRef(null);
  const retryRef          = useRef(0);
  const retryTimerRef     = useRef(null);
  const aliveRef          = useRef(true);

  useEffect(() => {
    aliveRef.current = true;

    fetch(`${API_BASE}/api/machines/${machineId}/detail`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));

    const connect = () => {
      if (!aliveRef.current) return;
      const ws = new WebSocket(`${WS_BASE}/api/machines/ws/${machineId}/detail`);
      wsRef.current = ws;
      ws.onopen    = () => { retryRef.current = 0; };
      ws.onmessage = (ev) => { try { setData(JSON.parse(ev.data)); } catch {} };
      ws.onclose   = () => {
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
  }, [machineId]);

  if (error)  return <div className="md-error">Erro ao carregar: {error}</div>;
  if (!data)  return <div className="md-loading"><div className="md-spinner" />Carregando...</div>;
  if (data.erro) return <div className="md-error">{data.erro}</div>;

  const st = getStatus(data.status);

  return (
    <div className="md-root">

      {/* Breadcrumb */}
      <div className="md-breadcrumb">
        <Link to="/" className="md-bc-link">Chão de Fábrica</Link>
        <span className="md-bc-sep"> / </span>
        <span className="md-bc-current">{data.nome}</span>
      </div>

      {/* Header */}
      <div className="md-header">
        <div className="md-header-left">
          <div className="md-header-title-row">
            <h1 className="md-machine-name">{data.nome}</h1>
            <span className="md-status-badge" style={{ color: st.color, background: st.bg }}>
              {st.label}
            </span>
          </div>
          {data.peca_atual && (
            <div className="md-peca">
              Produto Atual: <strong>{data.peca_atual}</strong>
            </div>
          )}
        </div>

        <div className="md-header-right">
          {data.operador && (
            <div className="md-operator">
              <div className="md-op-avatar">{data.operador_avatar || "?"}</div>
              <div className="md-op-info">
                <div className="md-op-name">{data.operador}</div>
                <div className="md-op-role">Operador</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="md-kpis">
        <KpiCard label="OEE MÉDIO"       value={data.oee}             sub="vs. meta 85%" />
        <KpiCard label="DISPONIBILIDADE" value={data.disponibilidade} sub="Tempo rodando"  color="#2563eb" />
        <KpiCard label="PERFORMANCE"     value={data.performance}     sub="Ciclo padrão"   color="#7c3aed" />
        <KpiCard label="QUALIDADE"       value={data.qualidade}       sub="Refugo baixo"   color="#0891b2" />
      </div>

      {/* Bottom */}
      <div className="md-bottom">

        {/* Índices de Manutenção */}
        <div className="md-card md-maintenance">
          <div className="md-card-title">Índices de Manutenção</div>
          <MtbfRow label="MTBF (Médio entre falhas)"     value={data.manutencao?.mtbf} />
          <MtbfRow label="MTTR (Médio para reparo)"      value={data.manutencao?.mttr} />
          <MtbfRow label="MTTA (Médio para atendimento)" value={data.manutencao?.mtta} />
          <DonutChart mtbf={data.manutencao?.mtbf} mttr={data.manutencao?.mttr} />
        </div>

        <div className="md-stops-col">
          {/* Registros de Paradas */}
          <div className="md-card md-stops">
            <div className="md-card-title">Registros de Paradas</div>
            {data.registros_parada?.filter(p => p.codigo < 54).length > 0 ? (
              <table className="md-stops-table">
                <thead>
                  <tr>
                    <th>Início</th>
                    <th>Motivo</th>
                    <th>Duração</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.registros_parada.filter(p => p.codigo < 54).map((p, i) => (
                    <tr key={i}>
                      <td>{p.inicio}</td>
                      <td>{p.motivo || "-"}</td>
                      <td>{p.duracao}</td>
                      <td><span className="md-stop-badge">{p.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="md-no-stops">Nenhuma parada registrada no período.</div>
            )}
          </div>
          {/* Registros de Manutenção */}
          <div className="md-card md-stops">
            <div className="md-card-title">Registros de Manutenção</div>
            {data.registros_parada?.filter(p => p.codigo >= 54).length > 0 ? (
              <table className="md-stops-table">
                <thead>
                  <tr>
                    <th>Início</th>
                    <th>Motivo</th>
                    <th>Duração</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.registros_parada.filter(p => p.codigo >= 54).map((p, i) => (
                    <tr key={i}>
                      <td>{p.inicio}</td>
                      <td>{p.motivo || "-"}</td>
                      <td>{p.duracao}</td>
                      <td><span className="md-stop-badge">{p.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="md-no-stops">Nenhuma manutenção registrada no período.</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
