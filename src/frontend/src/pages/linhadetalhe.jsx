import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import "./linhadetalhe.css";
import "./Manutencao.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE  = API_BASE.replace(/^http/, "ws");

// ── helpers ──────────────────────────────────────────────────────────────────

const STATUS_MAP = {
  produzindo:   { label: "PRODUZINDO",  color: "#16a34a", bg: "#dcfce7", dot: "#16a34a" },
  alerta:       { label: "ALERTA",      color: "#d97706", bg: "#fef3c7", dot: "#d97706" },
  aguardando:   { label: "AGUARDANDO",  color: "#d97706", bg: "#fef3c7", dot: "#d97706" },
  parada:       { label: "PARADA",      color: "#dc2626", bg: "#fee2e2", dot: "#dc2626" },
  "manutenção": { label: "MANUTENÇÃO",  color: "#6b7280", bg: "#f3f4f6", dot: "#6b7280" },
  limpeza:      { label: "LIMPEZA",     color: "#2563eb", bg: "#dbeafe", dot: "#2563eb" },
};

function getStatus(raw) {
  if (!raw) return { label: raw || "-", color: "#6b7280", bg: "#f3f4f6", dot: "#6b7280" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_MAP)) {
    if (key.includes(k)) return v;
  }
  return { label: raw, color: "#6b7280", bg: "#f3f4f6", dot: "#6b7280" };
}

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n) || val === null || val === undefined) return "#d1d5db";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function statusGeralColor(s) {
  if (!s || s === "Operação Normal") return "#22c55e";
  if (s.startsWith("Atenção")) return "#dc2626";
  return "#f59e0b";
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "-";
  return `${v}${suffix}`;
}

const STATUS_ORDER = ["produzindo", "limpeza", "alerta", "aguardando", "manutenção", "parada"];
function statusRank(s) {
  const k = (s || "").toLowerCase();
  const i = STATUS_ORDER.findIndex(o => k.includes(o));
  return i === -1 ? 10 : i;
}

// ── componentes base ──────────────────────────────────────────────────────────

function KpiCard({ label, children, accent }) {
  return (
    <div className="ld-kpi-card" style={accent ? { borderTop: `3px solid ${accent}` } : {}}>
      <div className="ld-kpi-label">{label}</div>
      <div className="ld-kpi-body">{children}</div>
    </div>
  );
}

function ProgressBar({ value, color }) {
  const pct = Math.min(Math.max(Number(value) || 0, 0), 100);
  return (
    <div className="ld-bar-track">
      <div className="ld-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function MetricRow({ label, value }) {
  const color = oeeColor(value);
  return (
    <div className="ld-metric-row">
      <span className="ld-metric-label">{label}</span>
      <ProgressBar value={value} color={color} />
      <span className="ld-metric-val" style={{ color }}>
        {value !== null && value !== undefined ? `${value}%` : "-"}
      </span>
    </div>
  );
}

function Avatar({ iniciais, cor, size = 32 }) {
  return (
    <div
      className="ld-avatar"
      style={{ width: size, height: size, background: cor || "#6b7280", fontSize: size * 0.35 }}
      title={iniciais}
    >
      {iniciais}
    </div>
  );
}

// ── OEE Chart ─────────────────────────────────────────────────────────────────

function OeeChart({ maquinas }) {
  const data = [...maquinas]
    .sort((a, b) => (b.oee || 0) - (a.oee || 0))
    .map(m => ({
      nome: m.nome.length > 14 ? m.nome.slice(0, 13) + "…" : m.nome,
      oee:  Number(m.oee) || 0,
      status: m.status,
    }));

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="ld-chart-tooltip">
        <div className="ld-chart-tooltip-name">{d.nome}</div>
        <div style={{ color: oeeColor(d.oee), fontWeight: 700, fontSize: 15 }}>{d.oee}%</div>
        <div className="ld-chart-tooltip-status">{d.status}</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 34)}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 40, left: 0, bottom: 4 }}>
        <XAxis
          type="number"
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          tickFormatter={v => `${v}%`}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="nome"
          width={110}
          tick={{ fontSize: 12, fill: "#374151" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f9fafb" }} />
        <ReferenceLine x={75} stroke="#16a34a" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "75%", position: "top", fontSize: 10, fill: "#16a34a" }} />
        <ReferenceLine x={50} stroke="#d97706" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "50%", position: "top", fontSize: 10, fill: "#d97706" }} />
        <Bar dataKey="oee" radius={[0, 6, 6, 0]} maxBarSize={22}>
          {data.map((entry, i) => (
            <Cell key={i} fill={oeeColor(entry.oee)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Status Distribution ───────────────────────────────────────────────────────

const STATUS_DIST_ITEMS = [
  { key: "produzindo", label: "Produzindo",  color: "#16a34a", bg: "#dcfce7" },
  { key: "alerta",     label: "Alerta",      color: "#d97706", bg: "#fef3c7" },
  { key: "parada",     label: "Parada",      color: "#dc2626", bg: "#fee2e2" },
  { key: "manutencao", label: "Manutenção",  color: "#6b7280", bg: "#f3f4f6" },
  { key: "limpeza",    label: "Limpeza",     color: "#2563eb", bg: "#dbeafe" },
];

function StatusDist({ dist, total }) {
  return (
    <div className="ld-status-dist">
      {STATUS_DIST_ITEMS.filter(item => dist[item.key] > 0 || item.key === "produzindo").map(item => {
        const count = dist[item.key] || 0;
        const pct   = total > 0 ? (count / total) * 100 : 0;
        return (
          <div key={item.key} className="ld-sd-row">
            <div className="ld-sd-label-group">
              <span className="ld-sd-dot" style={{ background: item.color }} />
              <span className="ld-sd-label">{item.label}</span>
            </div>
            <div className="ld-sd-bar-group">
              <div className="ld-sd-bar-track">
                <div
                  className="ld-sd-bar-fill"
                  style={{ width: `${pct}%`, background: item.color }}
                />
              </div>
              <span className="ld-sd-count" style={{ color: item.color }}>{count}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── OP Card ───────────────────────────────────────────────────────────────────

const OP_STATUS_LABELS = {
  em_andamento: { label: "Em andamento", color: "#16a34a", bg: "#dcfce7" },
  fila:         { label: "Na fila",      color: "#2563eb", bg: "#dbeafe" },
};

function OpCard({ op }) {
  const st = OP_STATUS_LABELS[op.status] || { label: op.status, color: "#6b7280", bg: "#f3f4f6" };
  const pct = Math.min(op.progresso, 100);
  const barColor = pct >= 100 ? "#16a34a" : pct >= 60 ? "#d97706" : "#2563eb";
  return (
    <div className="ld-op-card">
      <div className="ld-op-header">
        <div>
          <div className="ld-op-numero">{op.numero}</div>
          <div className="ld-op-peca">{op.peca}</div>
        </div>
        <span className="ld-op-badge" style={{ color: st.color, background: st.bg }}>{st.label}</span>
      </div>
      <div className="ld-op-progress-row">
        <div className="ld-op-bar-track">
          <div className="ld-op-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
        </div>
        <span className="ld-op-pct" style={{ color: barColor }}>{pct.toFixed(0)}%</span>
      </div>
      <div className="ld-op-footer">
        <span>{op.produzido.toLocaleString("pt-BR")} / {op.quantidade.toLocaleString("pt-BR")} un</span>
        {op.refugo > 0 && (
          <span className="ld-op-refugo">{op.refugo} refugo{op.refugo > 1 ? "s" : ""}</span>
        )}
      </div>
    </div>
  );
}

// ── MachineCard ───────────────────────────────────────────────────────────────

function MachineCard({ machine }) {
  const st = getStatus(machine.status);
  const isProduzindo = machine.status?.toLowerCase().includes("produz");
  const isParada = !isProduzindo;

  const oeeVal = machine.oee;
  const oc = oeeColor(oeeVal);

  return (
    <div className="ld-machine-card">
      {/* cabeçalho */}
      <div className="ld-mc-header">
        <div>
          <div className="ld-mc-name">{machine.nome}</div>
          <div className="ld-mc-tipo">{machine.tipo}</div>
        </div>
        <span className="ld-mc-badge" style={{ color: st.color, background: st.bg }}>
          <span className="ld-mc-dot" style={{ background: st.dot }} />
          {st.label}
        </span>
      </div>

      {/* OEE + OP/Peça */}
      <div className="ld-mc-oee-row">
        <div>
          <div className="ld-mc-oee-val" style={{ color: oc }}>
            {oeeVal !== null && oeeVal !== undefined ? `${oeeVal}%` : "-"}
          </div>
          <div className="ld-mc-oee-label">OEE DO TURNO</div>
        </div>

        {machine.op && (
          <div className="ld-mc-op-block">
            <div className="ld-mc-op">{machine.op}</div>
            <div className="ld-mc-peca">Peça: {machine.peca}</div>
          </div>
        )}

        {!machine.op && machine.peca && (
          <div className="ld-mc-op-block">
            <div className="ld-mc-peca">{machine.peca}</div>
          </div>
        )}

        {isParada && machine.motivo_parada && (
          <div className="ld-mc-motivo" style={{ color: st.color, background: st.bg }}>
            {machine.motivo_parada}
          </div>
        )}
      </div>

      {/* barras de métricas — sempre visíveis */}
      <div className="ld-mc-metrics">
        <MetricRow label="Disponibilidade" value={machine.disponibilidade} />
        <MetricRow label="Performance"     value={machine.performance} />
        <MetricRow label="Qualidade"       value={machine.qualidade} />
      </div>

      {/* contexto de parada (quando aplicável) */}
      {isParada && (machine.parada_ha || machine.manutencao || machine.engenheiro) && (
        <div className="ld-mc-parada-info">
          {machine.parada_ha && (
            <div className="ld-mc-parada-item">
              <span className="ld-mc-parada-label">PARADA HÁ</span>
              <span className="ld-mc-parada-val">{machine.parada_ha}</span>
            </div>
          )}
          {machine.manutencao && (
            <div className="ld-mc-parada-item">
              <span className="ld-mc-parada-label">MANUTENÇÃO</span>
              <span className="ld-mc-parada-val">{machine.manutencao}</span>
            </div>
          )}
          {machine.engenheiro && (
            <div className="ld-mc-parada-item">
              <span className="ld-mc-parada-label">ENGENHEIRO</span>
              <span className="ld-mc-parada-val">{machine.engenheiro}</span>
            </div>
          )}
        </div>
      )}

      {/* rodapé */}
      <div className="ld-mc-footer">
        <div className="ld-mc-foot-item">
          <span className="ld-mc-foot-label">PRODUZIDO</span>
          <span className="ld-mc-foot-val">{fmt(machine.produzido, " un")}</span>
        </div>
        {machine.rejeitos > 0 && (
          <div className="ld-mc-foot-item">
            <span className="ld-mc-foot-label">REJEITOS</span>
            <span className="ld-mc-foot-val" style={{ color: "#dc2626" }}>{machine.rejeitos} un</span>
          </div>
        )}
        {machine.ciclo_segundos && (
          <div className="ld-mc-foot-item">
            <span className="ld-mc-foot-label">CICLO</span>
            <span className="ld-mc-foot-val">{machine.ciclo_segundos}s</span>
          </div>
        )}
        {machine.operador && (
          <div className="ld-mc-foot-item ld-mc-operador">
            <Avatar iniciais={machine.operador_avatar} cor="#6b7280" size={24} />
            <span className="ld-mc-foot-val">{machine.operador}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Seção de OS da linha ──────────────────────────────────────────────────────

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

function OSLinhaSection({ lineId }) {
  const [osList,  setOsList]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/manutencao?linha_id=${lineId}&limite=30`)
      .then(r => r.json())
      .then(d => { setOsList(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [lineId]);

  if (loading || osList.length === 0) return null;

  const abertas    = osList.filter(o => o.status === "aberta" || o.status === "em_andamento");
  const concluidas = osList.filter(o => o.status === "concluida");
  const recentes   = osList.slice(0, expanded ? 20 : 5);
  const avgMttr    = concluidas.length > 0
    ? Math.round(concluidas.reduce((s, o) => s + (o.tempo_reparo_min ?? o.tempo_total_min ?? 0), 0) / concluidas.length)
    : null;

  return (
    <div className="ld-ops-section">
      <div className="ld-section-header">
        <h2 className="ld-section-title">🔧 Manutenção / OS</h2>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {avgMttr !== null && (
            <span style={{ fontSize: 13, color: "var(--muted,#6b7280)" }}>MTTR: <strong>{fmtMin(avgMttr)}</strong></span>
          )}
          {abertas.length > 0 && (
            <span className="man-status-badge aberta">{abertas.length} aberta{abertas.length > 1 ? "s" : ""}</span>
          )}
          <span className="ld-ops-count">{osList.length} OS</span>
        </div>
      </div>

      {/* Active OS cards */}
      {abertas.length > 0 && (
        <div className="man-active-grid" style={{ marginBottom: 16 }}>
          {abertas.map(o => (
            <div key={o.id_os} className={`man-os-card status-${o.status}`}>
              <div className="man-os-card-header">
                <div>
                  <div className="man-os-id">OS #{o.id_os}</div>
                  <div className="man-os-machine">{o.nome_ihm}</div>
                </div>
                <span className={`man-status-badge ${o.status}`}>{OS_STATUS_LABELS[o.status]}</span>
              </div>
              {o.motivo_abertura && <div className="man-os-motivo">{o.motivo_abertura}</div>}
              <div className="man-os-times">
                <span>Aberta: {fmtDtCurto(o.dt_abertura)}</span>
                {o.manutentor && <span>Manutentor: {o.manutentor}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* History table */}
      <table className="ld-os-table">
        <thead>
          <tr><th>OS</th><th>Máquina</th><th>Status</th><th>Abertura</th><th>Manutentor</th><th>Duração</th></tr>
        </thead>
        <tbody>
          {recentes.map(o => (
            <tr key={o.id_os}>
              <td style={{ fontSize: 12, color: "#6b7280" }}>#{o.id_os}</td>
              <td style={{ fontWeight: 600, fontSize: 13 }}>{o.nome_ihm}</td>
              <td><span className={`man-status-badge ${o.status}`}>{OS_STATUS_LABELS[o.status]}</span></td>
              <td style={{ fontSize: 12, color: "#6b7280" }}>{fmtDtCurto(o.dt_abertura)}</td>
              <td style={{ fontSize: 13 }}>{o.manutentor || "—"}</td>
              <td style={{ fontSize: 13 }}>{fmtMin(o.tempo_total_min)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {osList.length > 5 && (
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          style={{ marginTop: 8, fontSize: 13, color: "var(--brand,#2563eb)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
        >
          {expanded ? "Ver menos" : `Ver mais ${osList.length - 5} OS`}
        </button>
      )}
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

const FILTROS_MAQUINA = ["Todas", "Produzindo", "Paradas"];

export default function LinhaDetalhe() {
  const { lineId } = useParams();
  const navigate   = useNavigate();

  const [data,   setData]   = useState(null);
  const [error,  setError]  = useState(null);
  const [filtro, setFiltro] = useState("Todas");

  const wsRef = useRef(null);

  useEffect(() => {
    let alive = true;
    let retryCount = 0;
    let retryTimer = null;

    setData(null);
    setError(null);

    fetch(`${API_BASE}/api/lines/${lineId}/detail`)
      .then((r) => r.json())
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(String(e)); });

    const connect = () => {
      if (!alive) return;
      const ws = new WebSocket(`${WS_BASE}/api/lines/${lineId}/ws`);
      wsRef.current = ws;
      ws.onopen    = () => { retryCount = 0; };
      ws.onmessage = (ev) => { try { if (alive) setData(JSON.parse(ev.data)); } catch {} };
      ws.onclose   = () => {
        if (!alive) return;
        retryCount += 1;
        const delay = Math.min(1000 * 2 ** (retryCount - 1), 10000);
        retryTimer = setTimeout(connect, delay);
      };
    };
    connect();

    return () => {
      alive = false;
      if (retryTimer) clearTimeout(retryTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, [lineId]);

  if (error) return <div className="ld-error">Erro: {error}</div>;
  if (!data)  return <div className="ld-loading"><div className="ld-spinner" />Carregando...</div>;

  const { kpis } = data;
  const oeeC = oeeColor(kpis.oee_global);
  const sgColor = statusGeralColor(data.status_geral);

  // filtro de máquinas
  const maquinasFiltradas = [...data.maquinas]
    .sort((a, b) => statusRank(a.status) - statusRank(b.status))
    .filter(m => {
      if (filtro === "Produzindo") return m.status?.toLowerCase().includes("produz");
      if (filtro === "Paradas")   return !m.status?.toLowerCase().includes("produz");
      return true;
    });

  const prodMeta    = kpis.producao_meta || 0;
  const prodPct     = prodMeta > 0 ? Math.min((kpis.producao_hoje / prodMeta) * 100, 100) : 0;
  const prodBarColor = prodPct >= 90 ? "#16a34a" : prodPct >= 60 ? "#d97706" : "#dc2626";

  const totalMaq = kpis.maquinas_total || 0;
  const dist     = kpis.status_dist || {};

  return (
    <div className="ld-root">

      {/* ── Cabeçalho ───────────────────────────────────────── */}
      <div className="ld-page-header">
        <div className="ld-page-header-left">
          <h1 className="ld-page-title">{data.nome}</h1>
          <div className="ld-page-sub">
            <span className="ld-status-dot" style={{ background: sgColor }} />
            <span>{data.status_geral}</span>
            <span className="ld-sep">•</span>
            <span>Atualizado às {data.ultima_atualizacao}</span>
          </div>
        </div>
        <div className="ld-page-header-right">
          <button className="ld-btn-secondary" type="button" onClick={() => navigate("/historico")}>
            Histórico
          </button>
          <button className="ld-btn-primary" type="button" onClick={() => navigate("/ordens")}>
            Ver Ordens
          </button>
        </div>
      </div>

      {/* ── KPI cards ────────────────────────────────────────── */}
      <div className="ld-kpi-grid">

        {/* OEE Global */}
        <KpiCard label="OEE Global da Linha" accent={oeeC}>
          <div className="ld-kpi-oee">
            <span className="ld-kpi-oee-val" style={{ color: oeeC }}>{kpis.oee_global}%</span>
            {kpis.oee_variacao != null && (
              <span
                className="ld-kpi-oee-var"
                style={{ color: kpis.oee_variacao >= 0 ? "#16a34a" : "#dc2626" }}
              >
                {kpis.oee_variacao >= 0 ? "+" : ""}{kpis.oee_variacao}%
              </span>
            )}
          </div>
          <div className="ld-kpi-mini-bar">
            <div style={{ width: `${kpis.oee_global}%`, background: oeeC }} />
          </div>
        </KpiCard>

        {/* Produção */}
        <KpiCard label="Produção Hoje (Un)">
          <div className="ld-kpi-prod">
            <span className="ld-kpi-prod-val">
              {kpis.producao_hoje.toLocaleString("pt-BR")}
            </span>
            {prodMeta > 0 && (
              <span className="ld-kpi-prod-meta">
                / {prodMeta.toLocaleString("pt-BR")} meta
              </span>
            )}
          </div>
          {prodMeta > 0 && (
            <>
              <div className="ld-kpi-mini-bar">
                <div style={{ width: `${prodPct}%`, background: prodBarColor }} />
              </div>
              <div className="ld-kpi-previsao">
                <span style={{ color: prodBarColor, fontWeight: 700 }}>{prodPct.toFixed(0)}%</span>
                {" "}da meta
                {kpis.previsao_termino && (
                  <> · Previsão: <strong>{kpis.previsao_termino}</strong></>
                )}
              </div>
            </>
          )}
        </KpiCard>

        {/* Máquinas */}
        <KpiCard label="Máquinas Ativas">
          <div className="ld-kpi-maq">
            <span className="ld-kpi-maq-val">{kpis.maquinas_ativas}</span>
            <span className="ld-kpi-maq-sep">/</span>
            <span className="ld-kpi-maq-total">{totalMaq}</span>
          </div>
          <div className="ld-kpi-maq-label">
            {totalMaq - kpis.maquinas_ativas > 0
              ? `${totalMaq - kpis.maquinas_ativas} em parada ou manutenção`
              : "Todas em operação"}
          </div>
        </KpiCard>

        {/* Qualidade */}
        <KpiCard label="Qualidade Global" accent={oeeColor(kpis.qualidade_global)}>
          {kpis.qualidade_global != null ? (
            <>
              <div className="ld-kpi-oee">
                <span className="ld-kpi-oee-val" style={{ color: oeeColor(kpis.qualidade_global) }}>
                  {kpis.qualidade_global}%
                </span>
              </div>
              <div className="ld-kpi-mini-bar">
                <div style={{ width: `${kpis.qualidade_global}%`, background: oeeColor(kpis.qualidade_global) }} />
              </div>
              <div className="ld-kpi-previsao">peças aprovadas no turno</div>
            </>
          ) : (
            <div className="ld-kpi-maq-label">Sem produção registrada</div>
          )}
        </KpiCard>

      </div>

      {/* ── Visão geral: gráfico OEE + distribuição ──────────── */}
      <div className="ld-overview-row">

        {/* OEE por máquina */}
        <div className="ld-card ld-chart-card">
          <div className="ld-card-title">OEE por Máquina</div>
          <div className="ld-chart-legend">
            <span style={{ color: "#16a34a" }}>● ≥ 75%</span>
            <span style={{ color: "#d97706" }}>● ≥ 50%</span>
            <span style={{ color: "#dc2626" }}>● &lt; 50%</span>
          </div>
          <OeeChart maquinas={data.maquinas} />
        </div>

        {/* Distribuição de status */}
        <div className="ld-card ld-dist-card">
          <div className="ld-card-title">Status das Máquinas</div>
          <div className="ld-dist-total">{totalMaq} máquinas no total</div>
          <StatusDist dist={dist} total={totalMaq} />
        </div>

      </div>

      {/* ── OPs Ativas ───────────────────────────────────────── */}
      {data.ops_ativas && data.ops_ativas.length > 0 && (
        <div className="ld-ops-section">
          <div className="ld-section-header">
            <h2 className="ld-section-title">Ordens de Produção Ativas</h2>
            <span className="ld-ops-count">{data.ops_ativas.length} OP{data.ops_ativas.length > 1 ? "s" : ""}</span>
          </div>
          <div className="ld-ops-grid">
            {data.ops_ativas.map(op => <OpCard key={op.id} op={op} />)}
          </div>
        </div>
      )}

      {/* ── OS da linha ──────────────────────────────────────── */}
      <OSLinhaSection lineId={lineId} />

      {/* ── Grid de máquinas ─────────────────────────────────── */}
      <div className="ld-machines-section">
        <div className="ld-machines-header">
          <div className="ld-machines-header-left">
            <h2 className="ld-machines-title">Máquinas</h2>
            <div className="ld-tab-group">
              {FILTROS_MAQUINA.map(f => (
                <button
                  key={f}
                  type="button"
                  className={"ld-tab" + (filtro === f ? " active" : "")}
                  onClick={() => setFiltro(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>

        {maquinasFiltradas.length === 0 ? (
          <div className="ld-empty">Nenhuma máquina neste filtro.</div>
        ) : (
          <div className="ld-machine-grid">
            {maquinasFiltradas.map(m => (
              <MachineCard key={m.id} machine={m} />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
