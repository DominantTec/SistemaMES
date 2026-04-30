import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip,
  ResponsiveContainer, ReferenceLine,
  AreaChart, Area, CartesianGrid,
} from "recharts";
import "./MaquinaDetalhe.css";
import "./Manutencao.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE  = API_BASE.replace(/^http/, "ws");

// ── helpers ───────────────────────────────────────────────────────────────────

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
  if (isNaN(n) || val === null || val === undefined) return "#d1d5db";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function fmtDurS(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(ss).padStart(2, "0")}s`;
  return `${s}s`;
}

function fmtUptime(s) {
  if (!s && s !== 0) return null;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m sem parar`;
  if (m > 0) return `${m}m sem parar`;
  return `< 1min sem parar`;
}

function parseHM(str) {
  if (!str || str === "-") return 0;
  const m = str.match(/(\d+)h\s*(\d+)m/);
  return m ? parseInt(m[1]) * 3600 + parseInt(m[2]) * 60 : 0;
}

// ── KPI card com barra de progresso ──────────────────────────────────────────

function KpiCard({ label, value, sub, color, suffix = "%" }) {
  const n   = Number(value);
  const c   = color || oeeColor(value);
  const pct = isNaN(n) ? 0 : Math.max(0, Math.min(100, n));
  return (
    <div className="md-kpi-card" style={{ borderTop: `3px solid ${c}` }}>
      <div className="md-kpi-label">{label}</div>
      <div className="md-kpi-value" style={{ color: c }}>
        {value !== null && value !== undefined && value !== "-" ? `${value}${suffix}` : "-"}
      </div>
      <div className="md-kpi-bar-track">
        <div className="md-kpi-bar-fill" style={{ width: `${pct}%`, background: c }} />
      </div>
      {sub && <div className="md-kpi-sub">{sub}</div>}
    </div>
  );
}

// ── Card de produção ──────────────────────────────────────────────────────────

function ProdKpiCard({ produzido, meta, pct, velocidade }) {
  const pctNum   = Math.max(0, Number(pct) || 0);
  const barColor = pctNum >= 90 ? "#16a34a" : pctNum >= 60 ? "#d97706" : "#dc2626";
  return (
    <div className="md-kpi-card md-kpi-prod-card" style={{ borderTop: `3px solid ${barColor}` }}>
      <div className="md-kpi-label">PRODUÇÃO DO TURNO</div>
      <div className="md-kpi-prod-main">
        <span className="md-kpi-prod-val">{(produzido || 0).toLocaleString("pt-BR")}</span>
        {meta > 0 && (
          <span className="md-kpi-prod-meta">/ {meta.toLocaleString("pt-BR")} un</span>
        )}
      </div>
      <div className="md-kpi-bar-track">
        <div
          className="md-kpi-bar-fill"
          style={{ width: `${Math.min(100, pctNum)}%`, background: barColor }}
        />
      </div>
      <div className="md-kpi-sub">
        <span style={{ color: barColor, fontWeight: 700 }}>{pctNum.toFixed(0)}%</span>
        {" "}da meta
        {velocidade > 0 && (
          <> · <strong>{velocidade.toLocaleString("pt-BR")}</strong> pcs/h</>
        )}
      </div>
    </div>
  );
}

// ── Card de Refugo ────────────────────────────────────────────────────────────

function RefugoCard({ refugo, pct }) {
  const p   = Number(pct) || 0;
  const c   = p === 0 ? "#16a34a" : p < 5 ? "#d97706" : "#dc2626";
  return (
    <div className="md-kpi-card" style={{ borderTop: `3px solid ${c}` }}>
      <div className="md-kpi-label">REFUGO DO TURNO</div>
      <div className="md-kpi-value" style={{ color: c }}>
        {(refugo || 0).toLocaleString("pt-BR")}
        <span className="md-kpi-value-unit"> un</span>
      </div>
      <div className="md-kpi-bar-track">
        <div className="md-kpi-bar-fill" style={{ width: `${Math.min(100, p * 4)}%`, background: c }} />
      </div>
      <div className="md-kpi-sub">
        <span style={{ color: c, fontWeight: 700 }}>{p.toFixed(1)}%</span>
        {" "}das peças produzidas
      </div>
    </div>
  );
}

// ── OP compacta (header) ──────────────────────────────────────────────────────

function OpCompacta({ op }) {
  const pct      = Math.min(100, op.progresso || 0);
  const barColor = pct >= 90 ? "#16a34a" : pct >= 60 ? "#d97706" : "#2563eb";
  return (
    <div className="md-op-compacta">
      <div className="md-op-c-top">
        <span className="md-op-c-num">{op.numero}</span>
        <span className="md-op-c-peca">{op.peca}</span>
      </div>
      <div className="md-op-c-bar-track">
        <div className="md-op-c-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <div className="md-op-c-footer">
        <span>{op.produzido.toLocaleString("pt-BR")} / {op.quantidade.toLocaleString("pt-BR")} un</span>
        {op.refugo > 0 && (
          <span className="md-op-c-refugo">{op.refugo} refugo{op.refugo > 1 ? "s" : ""}</span>
        )}
        <span style={{ color: barColor, fontWeight: 700, marginLeft: "auto" }}>
          {pct.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

// ── Info strip ────────────────────────────────────────────────────────────────

function InfoStrip({ tipoMaquina, operador, manutentor, uptimeS, peca }) {
  const uptimeTxt = fmtUptime(uptimeS);
  return (
    <div className="md-info-strip">
      {tipoMaquina && (
        <div className="md-info-chip md-info-chip-tipo">
          <span className="md-info-chip-icon">⚙</span>
          <span className="md-info-chip-label">Tipo</span>
          <span className="md-info-chip-val">{tipoMaquina}</span>
        </div>
      )}
      {peca && (
        <div className="md-info-chip">
          <span className="md-info-chip-icon">◈</span>
          <span className="md-info-chip-label">Produto</span>
          <span className="md-info-chip-val">{peca}</span>
        </div>
      )}
      {operador && (
        <div className="md-info-chip">
          <span className="md-info-chip-icon">◎</span>
          <span className="md-info-chip-label">Operador</span>
          <span className="md-info-chip-val">{operador}</span>
        </div>
      )}
      {manutentor && (
        <div className="md-info-chip">
          <span className="md-info-chip-icon">▲</span>
          <span className="md-info-chip-label">Manutentor</span>
          <span className="md-info-chip-val">{manutentor}</span>
        </div>
      )}
      {uptimeTxt && (
        <div className="md-info-chip md-info-chip-uptime">
          <span className="md-info-chip-icon">●</span>
          <span className="md-info-chip-val">{uptimeTxt}</span>
        </div>
      )}
    </div>
  );
}

// ── Timeline do turno ─────────────────────────────────────────────────────────

const _TL_LEGEND_ORDER = [
  { status: 49, label: "Produzindo",      color: "#16a34a" },
  { status: 0,  label: "Parada",          color: "#dc2626" },
  { status: 52, label: "Manutenção",      color: "#7c3aed" },
  { status: 51, label: "Ag. Manutentor",  color: "#d97706" },
  { status: 4,  label: "Limpeza",         color: "#2563eb" },
];

function ShiftTimeline({ timeline, agoraPct, shiftInicio, shiftFim }) {
  const [hovered, setHovered] = useState(null);
  const usedSet     = new Set(timeline.map(s => s.status));
  const legendItems = _TL_LEGEND_ORDER.filter(l => usedSet.has(l.status));

  return (
    <div className="md-timeline">
      <div className="md-tl-time-labels">
        <span>{shiftInicio}</span>
        <span className="md-tl-agora-label">AGORA</span>
        <span>{shiftFim}</span>
      </div>
      <div className="md-tl-track" onMouseLeave={() => setHovered(null)}>
        {timeline.map((seg, i) => (
          <div
            key={i}
            className="md-tl-seg"
            style={{
              left:       `${seg.inicio_pct}%`,
              width:      `${Math.max(0.4, seg.fim_pct - seg.inicio_pct)}%`,
              background: seg.color,
            }}
            onMouseEnter={() => setHovered({ ...seg, _i: i })}
          />
        ))}
        {agoraPct != null && agoraPct < 99 && (
          <div className="md-tl-agora-line" style={{ left: `${agoraPct}%` }} />
        )}
        {hovered && (
          <div
            className="md-tl-tooltip"
            style={{
              left: `clamp(4px, ${(hovered.inicio_pct + hovered.fim_pct) / 2}%, calc(100% - 134px))`,
            }}
          >
            <div className="md-tl-tt-status" style={{ color: hovered.color }}>
              {hovered.label}
            </div>
            <div className="md-tl-tt-dur">{fmtDurS(hovered.duracao_s)}</div>
          </div>
        )}
      </div>
      {legendItems.length > 0 && (
        <div className="md-tl-legend">
          {legendItems.map(l => (
            <span key={l.status} className="md-tl-leg-item">
              <span className="md-tl-leg-dot" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Produção por hora ─────────────────────────────────────────────────────────

function ProducaoHorariaChart({ data, metaHora }) {
  if (!data?.length) {
    return <div className="md-chart-empty">Sem dados de produção no turno.</div>;
  }
  const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="md-chart-tooltip">
        <div className="md-ct-hora">{d.hora}</div>
        <div className="md-ct-val">{d.produzido.toLocaleString("pt-BR")} peças</div>
        {metaHora > 0 && (
          <div className="md-ct-meta">meta: {Math.round(metaHora)}</div>
        )}
      </div>
    );
  };
  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data} margin={{ top: 8, right: 14, left: -20, bottom: 4 }}>
        <XAxis dataKey="hora" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f9fafb" }} />
        {metaHora > 0 && (
          <ReferenceLine
            y={metaHora}
            stroke="#d97706"
            strokeDasharray="4 3"
            strokeWidth={1.5}
            label={{ value: "meta/h", position: "insideTopRight", fontSize: 10, fill: "#d97706" }}
          />
        )}
        <Bar dataKey="produzido" radius={[4, 4, 0, 0]} maxBarSize={44}>
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={
                metaHora <= 0                              ? "#3b82f6"
                : entry.produzido >= metaHora              ? "#16a34a"
                : entry.produzido >= metaHora * 0.7        ? "#d97706"
                : "#dc2626"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Tendência de disponibilidade por turno ────────────────────────────────────

function TendenciaTurnosChart({ historico }) {
  if (!historico?.length) {
    return (
      <div className="md-chart-empty">
        Dados históricos disponíveis após o encerramento do primeiro turno.
      </div>
    );
  }

  const TendTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    const c = d.disponibilidade >= 75 ? "#16a34a" : d.disponibilidade >= 50 ? "#d97706" : "#dc2626";
    return (
      <div className="md-chart-tooltip">
        <div className="md-ct-hora">{d.nome} · {d.data} {d.hora}</div>
        <div className="md-ct-val" style={{ color: c }}>{d.disponibilidade}% disponível</div>
        <div className="md-ct-meta">{d.num_paradas} parada{d.num_paradas !== 1 ? "s" : ""}</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={historico} margin={{ top: 8, right: 14, left: -20, bottom: 4 }}>
        <defs>
          <linearGradient id="gradDisp" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.18} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="data"
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={v => `${v}%`}
        />
        <Tooltip content={<TendTooltip />} />
        <ReferenceLine
          y={75}
          stroke="#16a34a"
          strokeDasharray="4 3"
          strokeWidth={1.2}
          label={{ value: "75%", position: "insideTopRight", fontSize: 10, fill: "#16a34a" }}
        />
        <Area
          type="monotone"
          dataKey="disponibilidade"
          stroke="#3b82f6"
          strokeWidth={2.5}
          fill="url(#gradDisp)"
          dot={{ r: 4, fill: "#3b82f6", stroke: "white", strokeWidth: 2 }}
          activeDot={{ r: 6 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Pareto de motivos ─────────────────────────────────────────────────────────

function ParetoChart({ pareto }) {
  if (!pareto?.length) {
    return <div className="md-chart-empty">Sem paradas registradas no turno.</div>;
  }
  const data = pareto.slice(0, 7).map(p => ({
    name: p.motivo.length > 22 ? p.motivo.slice(0, 21) + "…" : p.motivo,
    min:  Math.round(p.minutos * 10) / 10,
    pct:  p.percentual,
  }));
  const ParetoTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="md-chart-tooltip">
        <div style={{ fontWeight: 600 }}>{d.name}</div>
        <div className="md-ct-val">{d.min} min</div>
        <div className="md-ct-meta">{d.pct}% do tempo parado</div>
      </div>
    );
  };
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 38)}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 36, left: 0, bottom: 4 }}>
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: "#9ca3af" }}
          tickFormatter={v => `${v}m`}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={148}
          tick={{ fontSize: 11, fill: "#374151" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<ParetoTooltip />} cursor={{ fill: "#f9fafb" }} />
        <Bar dataKey="min" fill="#dc2626" radius={[0, 4, 4, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Índices de manutenção ─────────────────────────────────────────────────────

function MtbfRow({ label, value, suffix = "", hint }) {
  return (
    <div className="md-mtbf-row">
      <div className="md-mtbf-row-main">
        <span className="md-mtbf-label">{label}</span>
        <span className="md-mtbf-value">
          {value != null && value !== "-" ? `${value}${suffix}` : "-"}
        </span>
      </div>
      {hint && <div className="md-mtbf-hint">{hint}</div>}
    </div>
  );
}

function DonutChart({ mtbf, mttr }) {
  const vMtbf = parseHM(mtbf);
  const vMttr = parseHM(mttr);
  const total  = vMtbf + vMttr;
  if (total === 0) {
    return <div className="md-donut-empty">Sem dados suficientes para o gráfico</div>;
  }
  const SIZE  = 140;
  const THICK = 26;
  const r     = (SIZE - THICK) / 2;
  const circ  = 2 * Math.PI * r;
  const pctOp = vMtbf / total;
  const segs  = [
    { pct: pctOp,      color: "#16a34a", label: "MTBF", value: mtbf },
    { pct: 1 - pctOp,  color: "#dc2626", label: "MTTR", value: mttr },
  ];
  let cumAngle = -90;
  return (
    <div className="md-donut-wrap">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {segs.map((seg, i) => {
          const dash = seg.pct * circ;
          const gap  = circ - dash;
          const rot  = cumAngle;
          cumAngle  += seg.pct * 360;
          return (
            <circle key={i}
              cx={SIZE/2} cy={SIZE/2} r={r}
              fill="none" stroke={seg.color}
              strokeWidth={THICK}
              strokeDasharray={`${dash} ${gap}`}
              strokeLinecap="butt"
              transform={`rotate(${rot} ${SIZE/2} ${SIZE/2})`}
            />
          );
        })}
        <text x={SIZE/2} y={SIZE/2 - 5}  textAnchor="middle" className="md-donut-pct" fill="#111827">
          {Math.round(pctOp * 100)}%
        </text>
        <text x={SIZE/2} y={SIZE/2 + 11} textAnchor="middle" className="md-donut-sub" fill="#6b7280">
          operando
        </text>
      </svg>
      <div className="md-donut-legend">
        {segs.map(seg => (
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

// ── Seção de Manutenção (cards interpretativos) ───────────────────────────────

function ManutencaoSection({ manutencao, numParadas }) {
  const mtbfS = manutencao?.mtbf_s || 0;
  const mttrS = manutencao?.mttr_s || 0;

  const mtbfHint = mtbfS > 0
    ? `A máquina para em média a cada ${fmtDurS(mtbfS)}`
    : null;
  const mttrHint = mttrS > 0
    ? `Cada parada dura em média ${fmtDurS(mttrS)}`
    : null;

  const dispManut = mtbfS + mttrS > 0
    ? Math.round(mtbfS / (mtbfS + mttrS) * 100)
    : null;

  return (
    <div className="md-manut-section">
      <MtbfRow
        label="MTBF — Tempo entre falhas"
        value={manutencao?.mtbf}
        hint={mtbfHint}
      />
      <MtbfRow
        label="MTTR — Tempo médio de reparo"
        value={manutencao?.mttr}
        hint={mttrHint}
      />
      <MtbfRow
        label="Paradas registradas"
        value={numParadas}
        suffix=" eventos"
      />

      {dispManut !== null && (
        <div className="md-manut-disp-bar">
          <div className="md-manut-disp-label">
            <span>Disponibilidade (MTBF/MTTR)</span>
            <span style={{ color: dispManut >= 75 ? "#16a34a" : dispManut >= 50 ? "#d97706" : "#dc2626", fontWeight: 700 }}>
              {dispManut}%
            </span>
          </div>
          <div className="md-manut-disp-track">
            <div
              className="md-manut-disp-fill"
              style={{
                width: `${dispManut}%`,
                background: dispManut >= 75 ? "#16a34a" : dispManut >= 50 ? "#d97706" : "#dc2626",
              }}
            />
          </div>
        </div>
      )}

      <DonutChart mtbf={manutencao?.mtbf} mttr={manutencao?.mttr} />
    </div>
  );
}

// ── Helpers OS ────────────────────────────────────────────────────────────────

function fmtMin(min) {
  if (min == null) return "—";
  if (min < 60) return `${min}m`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}
function fmtDtCurto(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
const OS_STATUS_LABELS = { aberta: "Aberta", em_andamento: "Em Andamento", concluida: "Concluída", cancelada: "Cancelada" };

// ── Seção de OS da máquina ────────────────────────────────────────────────────

function OSHistoricoMaquina({ machineId }) {
  const [osList,  setOsList]  = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/manutencao?maquina_id=${machineId}&limite=15`)
      .then(r => r.json())
      .then(d => { setOsList(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [machineId]);

  if (loading || osList.length === 0) return null;

  const abertas    = osList.filter(o => o.status === "aberta" || o.status === "em_andamento");
  const concluidas = osList.filter(o => o.status === "concluida");
  const avgMttr    = concluidas.length > 0
    ? Math.round(concluidas.reduce((s, o) => s + (o.tempo_reparo_min ?? o.tempo_total_min ?? 0), 0) / concluidas.length)
    : null;

  return (
    <div className="md-card">
      <div className="md-card-title">
        Ordens de Serviço
        <span className="md-card-title-sub">últimas {osList.length}</span>
        {abertas.length > 0 && (
          <span className="md-card-count md-card-count-man">{abertas.length} ativa{abertas.length > 1 ? "s" : ""}</span>
        )}
      </div>

      {/* mini stats */}
      <div style={{ display: "flex", gap: 20, marginBottom: 14, flexWrap: "wrap" }}>
        {avgMttr !== null && (
          <div>
            <div style={{ fontSize: 11, color: "var(--muted,#6b7280)", fontWeight: 600, textTransform: "uppercase" }}>MTTR médio</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{fmtMin(avgMttr)}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, color: "var(--muted,#6b7280)", fontWeight: 600, textTransform: "uppercase" }}>Concluídas</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "#22c55e" }}>{concluidas.length}</div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--muted,#6b7280)", fontWeight: 600, textTransform: "uppercase" }}>Em aberto</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: abertas.length > 0 ? "#ef4444" : "#9ca3af" }}>{abertas.length}</div>
        </div>
      </div>

      <table className="md-stops-table">
        <thead>
          <tr><th>OS</th><th>Status</th><th>Abertura</th><th>Manutentor</th><th>Duração</th><th>Problema / Motivo</th></tr>
        </thead>
        <tbody>
          {osList.map(o => (
            <tr key={o.id_os}>
              <td className="md-stop-time">#{o.id_os}</td>
              <td>
                <span className={`man-status-badge ${o.status}`}>
                  {OS_STATUS_LABELS[o.status] ?? o.status}
                </span>
              </td>
              <td className="md-stop-time">{fmtDtCurto(o.dt_abertura)}</td>
              <td>{o.manutentor || "—"}</td>
              <td>
                <span className="md-stop-dur">{fmtMin(o.tempo_total_min)}</span>
              </td>
              <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {o.problema || o.motivo_abertura || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

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
      .then(r => r.json())
      .then(setData)
      .catch(e => setError(String(e)));

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

  if (error)     return <div className="md-error">Erro ao carregar: {error}</div>;
  if (!data)     return <div className="md-loading"><div className="md-spinner" />Carregando...</div>;
  if (data.erro) return <div className="md-error">{data.erro}</div>;

  const st = getStatus(data.status);

  const horas    = data.producao_horaria?.length || 0;
  const metaHora = horas > 0 && data.meta > 0 ? data.meta / horas : 0;

  const nParadas    = data.registros_parada?.filter(p => p.codigo < 54).length ?? 0;
  const nManutencao = data.registros_parada?.filter(p => p.codigo >= 54).length ?? 0;

  const isRunning = st.label === "EM OPERAÇÃO";

  return (
    <div className="md-root">

      {/* ── Breadcrumb ─────────────────────────────────────────────── */}
      <div className="md-breadcrumb">
        <Link to="/" className="md-bc-link">Chão de Fábrica</Link>
        <span className="md-bc-sep"> / </span>
        <span className="md-bc-link" style={{ cursor: "default" }}>{data.linha}</span>
        <span className="md-bc-sep"> / </span>
        <span className="md-bc-current">{data.nome}</span>
      </div>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="md-header">
        <div className="md-header-left">
          <div className="md-header-title-row">
            <h1 className="md-machine-name">{data.nome}</h1>
            <span className="md-status-badge" style={{ color: st.color, background: st.bg }}>
              <span className={`md-status-dot${isRunning ? " md-status-dot-pulse" : ""}`}
                    style={{ background: st.color }} />
              {st.label}
            </span>
            <span className="md-linha-tag">{data.linha}</span>
          </div>
          {data.parada_ha && (
            <div className="md-parada-ha" style={{ color: st.color }}>
              Parada há {data.parada_ha}
            </div>
          )}
        </div>

        <div className="md-header-right">
          {data.op_ativa && <OpCompacta op={data.op_ativa} />}
        </div>
      </div>

      {/* ── Info strip ─────────────────────────────────────────────── */}
      <InfoStrip
        tipoMaquina={data.tipo_maquina}
        peca={data.peca_atual}
        operador={data.operador}
        manutentor={data.manutentor}
        uptimeS={isRunning ? data.uptime_s : null}
      />

      {/* ── KPI strip ──────────────────────────────────────────────── */}
      <div className="md-kpis">
        <KpiCard
          label="OEE DO TURNO"
          value={data.oee}
          sub={`${data.num_paradas ?? 0} parada${data.num_paradas !== 1 ? "s" : ""} registradas`}
        />
        <KpiCard
          label="DISPONIBILIDADE"
          value={data.disponibilidade}
          sub="Tempo em produção"
          color="#2563eb"
        />
        <KpiCard
          label="PERFORMANCE"
          value={data.performance}
          sub="Ritmo vs. capacidade"
          color="#7c3aed"
        />
        <KpiCard
          label="QUALIDADE"
          value={data.qualidade}
          sub="Peças aprovadas"
          color="#0891b2"
        />
        <ProdKpiCard
          produzido={data.produzido}
          meta={data.meta}
          pct={data.producao_pct}
          velocidade={data.velocidade_pph}
        />
        <RefugoCard
          refugo={data.refugo_turno}
          pct={data.refugo_pct}
        />
      </div>

      {/* ── Timeline do turno ──────────────────────────────────────── */}
      {data.timeline_turno?.length > 0 && (
        <div className="md-card">
          <div className="md-card-title">
            Timeline do Turno
            <span className="md-card-title-sub">
              {data.shift_inicio} → {data.shift_fim}
            </span>
          </div>
          <ShiftTimeline
            timeline={data.timeline_turno}
            agoraPct={data.agora_pct}
            shiftInicio={data.shift_inicio}
            shiftFim={data.shift_fim}
          />
        </div>
      )}

      {/* ── Produção por hora + Tendência histórica ─────────────────── */}
      <div className="md-row">
        <div className="md-card">
          <div className="md-card-title">
            Produção por Hora
            <span className="md-card-title-sub">turno atual</span>
          </div>
          <ProducaoHorariaChart data={data.producao_horaria} metaHora={metaHora} />
        </div>

        <div className="md-card">
          <div className="md-card-title">
            Disponibilidade por Turno
            <span className="md-card-title-sub">últimos {data.historico_turnos?.length || 0} turnos</span>
          </div>
          <TendenciaTurnosChart historico={data.historico_turnos} />
        </div>
      </div>

      {/* ── Paradas + Pareto ───────────────────────────────────────── */}
      <div className="md-row md-row-equal">
        <div className="md-card">
          <div className="md-card-title">
            Paradas do Turno
            {nParadas > 0 && <span className="md-card-count">{nParadas}</span>}
          </div>
          {nParadas > 0 ? (
            <table className="md-stops-table">
              <thead>
                <tr><th>Início</th><th>Motivo</th><th>Duração</th></tr>
              </thead>
              <tbody>
                {data.registros_parada.filter(p => p.codigo < 54).map((p, i) => (
                  <tr key={i}>
                    <td className="md-stop-time">{p.inicio}</td>
                    <td>{p.motivo || "—"}</td>
                    <td><span className="md-stop-dur">{p.duracao}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="md-no-stops">Nenhuma parada registrada neste turno.</div>
          )}

          {nManutencao > 0 && (
            <>
              <div className="md-card-title md-card-title-inner">
                Manutenções
                <span className="md-card-count md-card-count-man">{nManutencao}</span>
              </div>
              <table className="md-stops-table">
                <thead>
                  <tr><th>Início</th><th>Motivo</th><th>Duração</th></tr>
                </thead>
                <tbody>
                  {data.registros_parada.filter(p => p.codigo >= 54).map((p, i) => (
                    <tr key={i}>
                      <td className="md-stop-time">{p.inicio}</td>
                      <td>{p.motivo || "—"}</td>
                      <td><span className="md-stop-dur md-stop-dur-man">{p.duracao}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>

        <div className="md-card">
          <div className="md-card-title">
            Motivos de Parada
            {data.pareto_paradas?.length > 0 && (
              <span className="md-card-count">{data.pareto_paradas.length}</span>
            )}
          </div>
          <ParetoChart pareto={data.pareto_paradas} />
        </div>
      </div>

      {/* ── Índices de manutenção ──────────────────────────────────── */}
      <div className="md-card">
        <div className="md-card-title">
          Análise de Confiabilidade
          <span className="md-card-title-sub">MTBF · MTTR · Disponibilidade</span>
        </div>
        <ManutencaoSection
          manutencao={data.manutencao}
          numParadas={data.num_paradas}
        />
      </div>

      {/* ── Ordens de Serviço desta máquina ───────────────────────── */}
      <OSHistoricoMaquina machineId={machineId} />

    </div>
  );
}
