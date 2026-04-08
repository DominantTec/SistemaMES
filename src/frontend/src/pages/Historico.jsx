import { useState, useEffect } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, ComposedChart, Line, ReferenceLine, Cell,
} from "recharts";
import "./historico.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function oeeColor(val) {
  const n = Number(val);
  if (isNaN(n) || val === "-") return "#6b7280";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function oeeLabel(val) {
  const n = Number(val);
  if (isNaN(n)) return "—";
  if (n >= 75) return "Ótimo";
  if (n >= 50) return "Regular";
  return "Crítico";
}

const STATUS_MAP = {
  produzindo:               { color: "#16a34a", bg: "#dcfce7", label: "Produzindo" },
  parada:                   { color: "#dc2626", bg: "#fee2e2", label: "Parada" },
  "aguardando manutentor":  { color: "#d97706", bg: "#fef3c7", label: "Ag. Manutentor" },
  "máquina em manutenção":  { color: "#7c3aed", bg: "#ede9fe", label: "Em Manutenção" },
  limpeza:                  { color: "#2563eb", bg: "#dbeafe", label: "Limpeza" },
};
function getStatus(raw) {
  if (!raw) return { color: "#9ca3af", bg: "#f3f4f6", label: "—" };
  const key = String(raw).toLowerCase();
  for (const [k, v] of Object.entries(STATUS_MAP)) {
    if (key.includes(k)) return v;
  }
  return { color: "#9ca3af", bg: "#f3f4f6", label: raw };
}

function toLocalDT(date) {
  const p = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth()+1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}`;
}

function fmtPct(v) {
  const n = Number(v);
  return isNaN(n) || v === "-" ? "—" : `${n}%`;
}

function encode(s) { return encodeURIComponent(s); }

// ─── Shared UI ────────────────────────────────────────────────────────────────

function Spinner({ size = 18 }) {
  return <div className="hi-spinner" style={{ width: size, height: size }} />;
}

function EmptyState({ icon = "📊", text }) {
  return (
    <div className="hi-empty">
      <div className="hi-empty-icon">{icon}</div>
      <div className="hi-empty-text">{text}</div>
    </div>
  );
}

function KPICard({ label, value, unit = "", sub, color, icon }) {
  return (
    <div className="hi-kpi-card">
      {icon && <div className="hi-kpi-icon">{icon}</div>}
      <div className="hi-kpi-label">{label}</div>
      <div className="hi-kpi-value" style={{ color: color || "var(--text)" }}>
        {value}{unit && <span className="hi-kpi-unit"> {unit}</span>}
      </div>
      {sub && <div className="hi-kpi-sub">{sub}</div>}
    </div>
  );
}

function ProgressBar({ value, color }) {
  const pct = Math.min(Math.max(Number(value) || 0, 0), 100);
  return (
    <div className="hi-bar-track">
      <div className="hi-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function StatusDot({ status }) {
  const s = getStatus(status);
  return (
    <span className="hi-status-dot" style={{ color: s.color, background: s.bg }}>{s.label}</span>
  );
}

// ─── Gauge SVG ────────────────────────────────────────────────────────────────

function GaugeArc({ value, label, size = 140 }) {
  const raw  = Number(value) || 0;
  const pct  = Math.min(raw, 100);
  const cx = 100, cy = 90, r = 70, sw = 12;
  const toRad = (d) => (d * Math.PI) / 180;
  const px = (d) => cx + r * Math.cos(toRad(d));
  const py = (d) => cy - r * Math.sin(toRad(d));
  const trackD = `M ${px(180)} ${py(180)} A ${r} ${r} 0 0 1 ${px(0)} ${py(0)}`;
  const fillAngle = 180 - Math.min(pct, 99.99) / 100 * 180;
  const fillD = pct > 0.1
    ? `M ${px(180)} ${py(180)} A ${r} ${r} 0 0 1 ${px(fillAngle)} ${py(fillAngle)}`
    : null;
  const needleLen = r - sw - 4;
  const needleAng = 180 - pct / 100 * 180;
  const ntx = cx + needleLen * Math.cos(toRad(needleAng));
  const nty = cy - needleLen * Math.sin(toRad(needleAng));
  const color = oeeColor(raw);

  return (
    <div className="hi-gauge-wrap">
      <svg viewBox="0 0 200 124" width={size} style={{ display: "block" }}>
        {[0, 25, 50, 75, 100].map((t) => {
          const a = 180 - t / 100 * 180;
          const r1 = r + sw / 2 + 2, r2 = r + sw / 2 + 8;
          return (
            <line key={t}
              x1={cx + r1 * Math.cos(toRad(a))} y1={cy - r1 * Math.sin(toRad(a))}
              x2={cx + r2 * Math.cos(toRad(a))} y2={cy - r2 * Math.sin(toRad(a))}
              stroke="#d1d5db" strokeWidth={1.5}
            />
          );
        })}
        <path d={trackD} fill="none" stroke="#e5e7eb" strokeWidth={sw} strokeLinecap="round" />
        {fillD && <path d={fillD} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" />}
        <line x1={cx} y1={cy} x2={ntx} y2={nty} stroke={color} strokeWidth={2.5} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={5} fill={color} />
        <circle cx={cx} cy={cy} r={2} fill="#fff" />
        <text x={cx} y={cy + 18} textAnchor="middle" fontSize="18" fontWeight="800"
              fill={color} fontFamily="system-ui" letterSpacing="-0.5">
          {raw !== null && !isNaN(raw) ? `${raw}%` : "—"}
        </text>
        <text x={cx} y={cy + 30} textAnchor="middle" fontSize="8.5" fill="#9ca3af" fontFamily="system-ui">
          {label}
        </text>
      </svg>
    </div>
  );
}

// ─── Recharts Tooltips ────────────────────────────────────────────────────────

function HourlyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="hi-tooltip">
      <div className="hi-tooltip-label">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="hi-tooltip-row">
          <span style={{ color: p.color }}>●</span>
          <span>{p.name}: <strong>{p.value}</strong> un</span>
        </div>
      ))}
    </div>
  );
}

function ParetoTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="hi-tooltip">
      <div className="hi-tooltip-label">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="hi-tooltip-row">
          <span style={{ color: p.color }}>●</span>
          <span>{p.name}: <strong>{p.value}{p.dataKey === "acumulado" ? "%" : " min"}</strong></span>
        </div>
      ))}
    </div>
  );
}

// ─── Charts ───────────────────────────────────────────────────────────────────

function HourlyChart({ data, height = 240 }) {
  if (!data || data.length === 0) return <EmptyState icon="📈" text="Sem dados de produção no período" />;
  const maxMeta = Math.max(...data.map((d) => d.meta || 0), 1);
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="hora" tick={{ fontSize: 11, fill: "#9ca3af" }} />
          <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} width={36} />
          <Tooltip content={<HourlyTooltip />} />
          {data[0]?.meta > 0 && (
            <ReferenceLine y={data[0].meta} stroke="#d97706" strokeDasharray="4 3"
              label={{ value: `Meta: ${data[0].meta}`, position: "insideTopRight", fontSize: 10, fill: "#d97706" }} />
          )}
          <Bar dataKey="produzido" name="Produzido" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={40}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.meta > 0 && entry.produzido >= entry.meta ? "#16a34a" : "#3b82f6"} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ParetoChart({ data, height = 240 }) {
  if (!data || data.length === 0) return <EmptyState icon="✅" text="Sem paradas registradas no período" />;
  const sliced = data.slice(0, 8);
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={sliced} layout="vertical" margin={{ top: 4, right: 50, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f4f6" />
          <XAxis type="number" tick={{ fontSize: 10, fill: "#9ca3af" }} />
          <YAxis type="category" dataKey="motivo" tick={{ fontSize: 10, fill: "#374151" }}
                 width={100} />
          <Tooltip content={<ParetoTooltip />} />
          <Bar dataKey="minutos" name="Minutos" fill="#f97316" radius={[0, 3, 3, 0]} maxBarSize={22}>
            {sliced.map((_, i) => (
              <Cell key={i} fill={i === 0 ? "#dc2626" : i < 3 ? "#f97316" : "#fbbf24"} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── OEE por Linha ───────────────────────────────────────────────────────────

function LinhasOEEChart({ linhas, height = 220 }) {
  if (!linhas || linhas.length === 0) return null;
  const data = linhas.map((l) => ({
    nome: l.nome,
    oee: typeof l.oee === "number" ? l.oee : 0,
  }));
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#9ca3af" }} width={36}
                 tickFormatter={(v) => `${v}%`} />
          <Tooltip
            formatter={(v) => [`${v}%`, "OEE"]}
            contentStyle={{ background: "#1f2937", border: "none", borderRadius: 8, fontSize: 12, color: "#f9fafb" }}
            itemStyle={{ color: "#f9fafb" }} labelStyle={{ color: "#9ca3af", fontWeight: 700 }}
          />
          <ReferenceLine y={75} stroke="#16a34a" strokeDasharray="5 3"
            label={{ value: "75% — Ótimo", position: "insideTopRight", fontSize: 10, fill: "#16a34a" }} />
          <ReferenceLine y={50} stroke="#d97706" strokeDasharray="5 3"
            label={{ value: "50% — Regular", position: "insideTopRight", fontSize: 10, fill: "#d97706" }} />
          <Bar dataKey="oee" name="OEE" radius={[4, 4, 0, 0]} maxBarSize={60}>
            {data.map((d, i) => <Cell key={i} fill={oeeColor(d.oee)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Produção vs Meta por Linha ───────────────────────────────────────────────

function ProdMetaChart({ linhas, height = 220 }) {
  if (!linhas || linhas.length === 0) return null;
  const data = linhas.map((l) => ({
    nome: l.nome,
    meta: l.meta_total || 0,
    produzido: l.realizado || 0,
  }));
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} width={42} />
          <Tooltip
            contentStyle={{ background: "#1f2937", border: "none", borderRadius: 8, fontSize: 12, color: "#f9fafb" }}
            itemStyle={{ color: "#f9fafb" }} labelStyle={{ color: "#9ca3af", fontWeight: 700 }}
          />
          <Bar dataKey="meta" name="Meta" fill="#e5e7eb" radius={[4, 4, 0, 0]} maxBarSize={28} />
          <Bar dataKey="produzido" name="Produzido" radius={[4, 4, 0, 0]} maxBarSize={28}>
            {data.map((d, i) => (
              <Cell key={i} fill={oeeColor(d.meta > 0 ? Math.round(d.produzido / d.meta * 100) : 0)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── OEE Breakdown por Máquina ────────────────────────────────────────────────

function MaquinasOEEChart({ maquinas, height = 240 }) {
  if (!maquinas || maquinas.length === 0) return null;
  const data = maquinas.map((m) => ({
    nome: m.nome,
    OEE:            typeof m.oee            === "number" ? m.oee            : 0,
    Disponibilidade: typeof m.disponibilidade === "number" ? m.disponibilidade : 0,
    Performance:    typeof m.performance    === "number" ? m.performance    : 0,
    Qualidade:      typeof m.qualidade      === "number" ? m.qualidade      : 0,
  }));
  const COLORS = { OEE: "#3b82f6", Disponibilidade: "#8b5cf6", Performance: "#f59e0b", Qualidade: "#10b981" };
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="nome" tick={{ fontSize: 10, fill: "#6b7280" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#9ca3af" }} width={36}
                 tickFormatter={(v) => `${v}%`} />
          <Tooltip
            formatter={(v, name) => [`${v}%`, name]}
            contentStyle={{ background: "#1f2937", border: "none", borderRadius: 8, fontSize: 12, color: "#f9fafb" }}
            itemStyle={{ color: "#f9fafb" }} labelStyle={{ color: "#9ca3af", fontWeight: 700 }}
          />
          <ReferenceLine y={75} stroke="#16a34a" strokeDasharray="4 3" />
          {Object.entries(COLORS).map(([key, color]) => (
            <Bar key={key} dataKey={key} fill={color} radius={[3, 3, 0, 0]} maxBarSize={18} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── MachineCard ──────────────────────────────────────────────────────────────

function MachineCard({ m, onClick }) {
  const st = getStatus(m.status);
  const oc = oeeColor(m.oee);
  return (
    <div className="hi-machine-card" onClick={onClick} style={onClick ? { cursor: "pointer" } : {}}>
      <div className="hi-machine-status-bar" style={{ background: st.color }} />
      <div className="hi-machine-body">
        <div className="hi-machine-header">
          <span className="hi-machine-name">{m.nome}</span>
          <span className="hi-machine-badge" style={{ color: st.color, background: st.bg }}>{st.label}</span>
        </div>
        <div className="hi-oee-block">
          <span className="hi-oee-label">OEE DO PERÍODO</span>
          <span className="hi-oee-value" style={{ color: oc }}>{fmtPct(m.oee)}</span>
        </div>
        <div className="hi-metrics">
          {[["Disp.", m.disponibilidade], ["Qual.", m.qualidade], ["Perf.", m.performance]].map(([lbl, val]) => (
            <div key={lbl} className="hi-metric-row">
              <span className="hi-metric-label">{lbl}</span>
              <ProgressBar value={val} color={oeeColor(val)} />
              <span className="hi-metric-value" style={{ color: oeeColor(val) }}>{fmtPct(val)}</span>
            </div>
          ))}
        </div>
        <div className="hi-prod-row">
          <span className="hi-prod-label">Prod.</span>
          <span className="hi-prod-value">
            <strong>{m.produzido}</strong>
            <span className="hi-prod-meta"> / {m.meta}</span>
          </span>
          {m.reprovado > 0 && (
            <span className="hi-reprovado">↓{m.reprovado} rej.</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Tab 1: Fábrica ───────────────────────────────────────────────────────────

function OrderFunnel({ funil }) {
  if (!funil) return null;
  const steps = [
    { key: "fila",        label: "Na Fila",     color: "#6b7280", icon: "📋" },
    { key: "em_producao", label: "Em Produção", color: "#3b82f6", icon: "⚙️" },
    { key: "finalizado",  label: "Finalizados", color: "#16a34a", icon: "✅" },
    { key: "cancelado",   label: "Cancelados",  color: "#dc2626", icon: "✗" },
  ];
  const maxQty = Math.max(...steps.map((s) => funil[s.key]?.qty || 0), 1);
  return (
    <div className="hi-funnel">
      {steps.map((s, i) => {
        const d = funil[s.key] || {};
        const pct = Math.round(100 * (d.qty || 0) / maxQty);
        return (
          <div key={s.key} className="hi-funnel-step">
            <div className="hi-funnel-bar-wrap">
              <div className="hi-funnel-bar" style={{
                width: `${Math.max(pct, 8)}%`,
                background: s.color,
                opacity: i === 3 ? 0.6 : 1,
              }} />
            </div>
            <div className="hi-funnel-info">
              <span className="hi-funnel-icon">{s.icon}</span>
              <span className="hi-funnel-label">{s.label}</span>
              <span className="hi-funnel-qty" style={{ color: s.color }}>
                <strong>{d.qty || 0}</strong> OPs
              </span>
              {d.pecas > 0 && (
                <span className="hi-funnel-pecas">{d.pecas} peças</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LineHeatCard({ linha }) {
  const oc = oeeColor(linha.oee || 0);
  const pct = linha.realizado_pct || 0;
  return (
    <div className="hi-heat-card" style={{ borderTopColor: oc }}>
      <div className="hi-heat-name">{linha.nome}</div>
      <div className="hi-heat-oee" style={{ color: oc }}>
        {linha.oee !== null && linha.oee !== undefined ? `${linha.oee}%` : "—"}
        <span className="hi-heat-oee-label"> OEE</span>
      </div>
      <div className="hi-heat-progress">
        <div className="hi-heat-progress-fill" style={{ width: `${Math.min(pct, 100)}%`, background: oc }} />
      </div>
      <div className="hi-heat-sub">
        <span>{linha.realizado} / {linha.meta_total} un</span>
        <span style={{ color: oc, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div className="hi-heat-machines">
        {linha.maquinas?.map((m) => (
          <div key={m.id} className="hi-heat-dot" style={{ background: oeeColor(m.oee) }}
               title={`${m.nome}: OEE ${fmtPct(m.oee)}`} />
        ))}
      </div>
    </div>
  );
}

function FabricaTab({ data, funil }) {
  if (!data) return <EmptyState icon="🏭" text="Selecione um período e clique em Buscar" />;

  const totalProd = data.linhas.reduce((s, l) => s + (l.realizado || 0), 0);
  const totalMeta = data.linhas.reduce((s, l) => s + (l.meta_total || 0), 0);
  const allOEEs   = data.linhas.flatMap((l) => l.maquinas.map((m) => m.oee)).filter((v) => typeof v === "number");
  const taxaRej   = data.linhas.flatMap((l) => l.maquinas).reduce((a, m) => {
    const p = typeof m.produzido === "number" ? m.produzido : 0;
    const r = typeof m.reprovado === "number" ? m.reprovado : 0;
    return { p: a.p + p, r: a.r + r };
  }, { p: 0, r: 0 });

  return (
    <div className="hi-tab-content">
      {/* KPIs globais */}
      <div className="hi-kpi-row">
        <KPICard
          icon="⚡"
          label="OEE Global"
          value={data.oee_global !== null ? `${data.oee_global}` : "—"}
          unit={data.oee_global !== null ? "%" : ""}
          color={oeeColor(data.oee_global)}
          sub={oeeLabel(data.oee_global)}
        />
        <KPICard
          icon="📦"
          label="Produção Total"
          value={totalProd.toLocaleString("pt-BR")}
          unit="un"
          color="#3b82f6"
          sub={`Meta: ${totalMeta.toLocaleString("pt-BR")} un · ${totalMeta > 0 ? Math.round(100 * totalProd / totalMeta) : 0}% atingido`}
        />
        <KPICard
          icon="🔍"
          label="Taxa de Rejeição"
          value={taxaRej.p + taxaRej.r > 0 ? `${((taxaRej.r / (taxaRej.p + taxaRej.r)) * 100).toFixed(1)}` : "0"}
          unit="%"
          color={taxaRej.r / Math.max(taxaRej.p + taxaRej.r, 1) > 0.1 ? "#dc2626" : "#16a34a"}
          sub={`${taxaRej.r} peças rejeitadas de ${taxaRej.p + taxaRej.r}`}
        />
        <KPICard
          icon="🏭"
          label="Linhas Monitoradas"
          value={data.linhas.length}
          sub={`${data.linhas.reduce((s, l) => s + (l.maquinas?.length || 0), 0)} máquinas no total`}
        />
      </div>

      {/* Mapa de calor das linhas */}
      <div className="hi-section">
        <div className="hi-section-header">
          <span className="hi-section-title">Mapa de Linhas</span>
          <span className="hi-section-sub">Performance por linha no período</span>
        </div>
        <div className="hi-heat-grid">
          {data.linhas.map((l) => <LineHeatCard key={l.id} linha={l} />)}
        </div>
      </div>

      {/* OEE e Produção por Linha */}
      <div className="hi-two-col">
        <div className="hi-section">
          <div className="hi-section-header">
            <span className="hi-section-title">OEE por Linha</span>
            <span className="hi-section-sub">Comparativo do período</span>
          </div>
          <LinhasOEEChart linhas={data.linhas} />
        </div>
        <div className="hi-section">
          <div className="hi-section-header">
            <span className="hi-section-title">Produção vs Meta</span>
            <span className="hi-section-sub">Realizado × planejado por linha</span>
          </div>
          <ProdMetaChart linhas={data.linhas} />
        </div>
      </div>

      {/* Funil de Ordens */}
      {funil && (
        <div className="hi-section">
          <div className="hi-section-header">
            <span className="hi-section-title">Funil de Ordens</span>
            <span className="hi-section-sub">Distribuição das OPs no período</span>
          </div>
          <OrderFunnel funil={funil} />
        </div>
      )}

      {/* Detalhe por linha */}
      <div className="hi-section">
        <div className="hi-section-header">
          <span className="hi-section-title">Detalhe por Linha</span>
        </div>
        {data.linhas.map((linha) => (
          <div key={linha.id} className="hi-line-section">
            <div className="hi-line-header">
              <div className="hi-line-header-left">
                <span className="hi-line-badge">{linha.nome}</span>
                <span className="hi-line-meta">
                  Produzido: <strong>{linha.realizado} un ({linha.realizado_pct}%)</strong>
                  {" · "}Meta: <strong>{linha.meta_total} un</strong>
                </span>
              </div>
              {linha.oee !== undefined && (
                <div className="hi-line-oee-badge" style={{ color: oeeColor(linha.oee), borderColor: oeeColor(linha.oee) }}>
                  OEE {fmtPct(linha.oee)}
                </div>
              )}
            </div>
            <div className="hi-machine-grid">
              {linha.maquinas.map((m) => <MachineCard key={m.id} m={m} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Tab 2: Linha ─────────────────────────────────────────────────────────────

function TurnosTable({ turnos }) {
  if (!turnos || turnos.length === 0) return <p className="hi-table-empty">Nenhum turno no período</p>;
  const statusStyle = { em_andamento: "#16a34a", finalizado: "#6b7280", agendado: "#3b82f6" };
  return (
    <div className="hi-table-wrap">
      <table className="hi-table">
        <thead>
          <tr>
            <th>Turno</th><th>Início</th><th>Fim</th><th>Status</th>
            <th>Meta</th><th>Produzido</th><th>Aderência</th>
          </tr>
        </thead>
        <tbody>
          {turnos.map((t, i) => (
            <tr key={i}>
              <td className="hi-td-name">{t.nome}</td>
              <td>{t.inicio}</td><td>{t.fim}</td>
              <td>
                <span className="hi-td-status" style={{ color: statusStyle[t.status] || "#6b7280" }}>
                  {t.status}
                </span>
              </td>
              <td>{t.meta}</td><td>{t.produzido}</td>
              <td>
                {t.aderencia !== null
                  ? <span style={{ color: oeeColor(t.aderencia), fontWeight: 700 }}>{t.aderencia}%</span>
                  : "—"
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrdensTable({ ordens }) {
  if (!ordens || ordens.length === 0) return <p className="hi-table-empty">Nenhuma ordem no período</p>;
  const stColor = { fila: "#6b7280", em_producao: "#3b82f6", finalizado: "#16a34a", cancelado: "#dc2626" };
  return (
    <div className="hi-table-wrap">
      <table className="hi-table">
        <thead>
          <tr>
            <th>OP</th><th>Peça</th><th>Qtd</th><th>Produzido</th>
            <th>Refugo</th><th>Conclusão</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {ordens.map((o, i) => (
            <tr key={i}>
              <td className="hi-td-name">{o.numero}</td>
              <td>{o.peca}</td><td>{o.quantidade}</td><td>{o.produzido}</td>
              <td style={{ color: o.refugo > 0 ? "#dc2626" : "inherit" }}>{o.refugo}</td>
              <td>
                <div className="hi-td-progress">
                  <div className="hi-td-bar" style={{ width: `${o.conclusao}%`, background: oeeColor(o.conclusao) }} />
                  <span style={{ color: oeeColor(o.conclusao) }}>{o.conclusao}%</span>
                </div>
              </td>
              <td>
                <span className="hi-td-status" style={{ color: stColor[o.status] || "#6b7280" }}>
                  {o.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LinhaTab({ linhas, inicio, fim }) {
  const [selectedId, setSelectedId]     = useState("");
  const [turnoOpts, setTurnoOpts]       = useState([]);
  const [selectedTurno, setSelectedTurno] = useState("");
  const [data, setData]                 = useState(null);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);

  // Busca turnos disponíveis ao selecionar a linha
  useEffect(() => {
    if (!selectedId) { setTurnoOpts([]); setSelectedTurno(""); return; }
    fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos/historico?limit=60`)
      .then((r) => r.json())
      .then((list) => {
        // Mostra apenas turnos finalizados ou em_andamento (com dados reais)
        const opts = list.filter((t) => t.status !== "agendado");
        setTurnoOpts(opts);
        setSelectedTurno("");
      })
      .catch(() => { setTurnoOpts([]); setSelectedTurno(""); });
  }, [selectedId]);

  function fmtTurnoLabel(t) {
    const dt = t.dt_real_inicio || t.dt_inicio;
    if (!dt) return t.nome;
    const d = new Date(dt);
    return `${t.nome} — ${d.toLocaleDateString("pt-BR")} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function analisar() {
    if (!selectedId) return;
    setLoading(true); setError(null); setData(null);
    const turnoParam = selectedTurno ? `&turno_id=${selectedTurno}` : "";
    fetch(`${API_BASE}/api/historico/linha/${selectedId}?data_inicio=${encode(inicio)}&data_fim=${encode(fim)}${turnoParam}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  return (
    <div className="hi-tab-content">
      <div className="hi-selector-bar">
        <select className="hi-select" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          <option value="">— Selecione uma linha —</option>
          {(linhas || []).map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <select
          className="hi-select"
          value={selectedTurno}
          onChange={(e) => setSelectedTurno(e.target.value)}
          disabled={!selectedId || turnoOpts.length === 0}
          title="Filtrar por turno específico (opcional)"
        >
          <option value="">Todos os turnos do período</option>
          {turnoOpts.map((t) => (
            <option key={t.id_ocorrencia} value={t.id_ocorrencia}>{fmtTurnoLabel(t)}</option>
          ))}
        </select>
        <button className="hi-buscar-btn" onClick={analisar} disabled={!selectedId || loading}>
          {loading ? <><Spinner size={14} /> Analisando...</> : "Analisar"}
        </button>
      </div>

      {error && <div className="hi-error">Erro: {error}</div>}
      {loading && <div className="hi-loading"><Spinner /> Carregando dados da linha...</div>}

      {data && !loading && (
        <>
          {/* KPIs */}
          <div className="hi-kpi-row">
            <KPICard icon="⚡" label="OEE da Linha" value={data.oee ?? "—"}
              unit={data.oee !== null ? "%" : ""} color={oeeColor(data.oee)}
              sub={oeeLabel(data.oee)} />
            <KPICard icon="📦" label="Produção Total" value={data.total_produzido?.toLocaleString("pt-BR")}
              unit="un" color="#3b82f6" sub={`${data.maquinas?.length || 0} máquinas na linha`} />
            <KPICard icon="🔍" label="Taxa de Rejeição" value={data.taxa_rejeicao}
              unit="%" color={data.taxa_rejeicao > 10 ? "#dc2626" : "#16a34a"}
              sub={`${data.total_reprovado} peças rejeitadas`} />
          </div>

          {/* Máquinas */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">OEE por Máquina</span>
            </div>
            <div className="hi-machine-grid">
              {data.maquinas?.map((m) => <MachineCard key={m.id} m={m} />)}
            </div>
          </div>

          {/* OEE breakdown por máquina */}
          {data.maquinas?.length > 1 && (
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">OEE Breakdown por Máquina</span>
                <span className="hi-section-sub">OEE · Disponibilidade · Performance · Qualidade</span>
              </div>
              <MaquinasOEEChart maquinas={data.maquinas} />
            </div>
          )}

          {/* Produção hora a hora */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">Produção Hora a Hora</span>
              <span className="hi-section-sub">Peças produzidas vs meta horária</span>
            </div>
            <HourlyChart data={data.producao_hora_a_hora} />
          </div>

          {/* Turnos + Ordens side by side */}
          <div className="hi-two-col">
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Turnos do Período</span>
              </div>
              <TurnosTable turnos={data.turnos} />
            </div>
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Ordens de Produção</span>
              </div>
              <OrdensTable ordens={data.ordens} />
            </div>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <EmptyState icon="🏭" text="Selecione uma linha e clique em Analisar" />
      )}
    </div>
  );
}

// ─── Tab 3: Máquina ───────────────────────────────────────────────────────────

function MaquinaTab({ linhas, inicio, fim }) {
  const [selectedLinhaId, setSelectedLinhaId] = useState("");
  const [selectedMaqId,   setSelectedMaqId]   = useState("");
  const [data,     setData]     = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  const selectedLinha = (linhas || []).find((l) => String(l.id) === String(selectedLinhaId));
  const maquinasOpts  = selectedLinha?.maquinas || [];

  useEffect(() => { setSelectedMaqId(""); setData(null); }, [selectedLinhaId]);

  function analisar() {
    if (!selectedMaqId) return;
    setLoading(true); setError(null); setData(null);
    fetch(`${API_BASE}/api/historico/maquina/${selectedMaqId}?data_inicio=${encode(inicio)}&data_fim=${encode(fim)}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  return (
    <div className="hi-tab-content">
      <div className="hi-selector-bar">
        <select className="hi-select" value={selectedLinhaId} onChange={(e) => setSelectedLinhaId(e.target.value)}>
          <option value="">— Selecione uma linha —</option>
          {(linhas || []).map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <select className="hi-select" value={selectedMaqId}
                onChange={(e) => setSelectedMaqId(e.target.value)} disabled={!selectedLinhaId}>
          <option value="">— Selecione uma máquina —</option>
          {maquinasOpts.map((m) => <option key={m.id} value={m.id}>{m.nome}</option>)}
        </select>
        <button className="hi-buscar-btn" onClick={analisar} disabled={!selectedMaqId || loading}>
          {loading ? <><Spinner size={14} /> Analisando...</> : "Analisar"}
        </button>
      </div>

      {error && <div className="hi-error">Erro: {error}</div>}
      {loading && <div className="hi-loading"><Spinner /> Carregando dados da máquina...</div>}

      {data && !loading && (
        <>
          {/* Header da máquina */}
          <div className="hi-maq-header">
            <div>
              <div className="hi-maq-title">{data.nome}</div>
              <div className="hi-maq-sub">{data.linha} · <StatusDot status={data.status} /></div>
            </div>
            {data.operador && data.operador !== "-" && (
              <div className="hi-maq-operador">
                <span className="hi-maq-op-icon">👷</span>
                <span>{data.operador}</span>
              </div>
            )}
          </div>

          {/* OEE triple gauge */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">OEE — Breakdown</span>
              <span className="hi-section-sub">Disponibilidade × Performance × Qualidade</span>
            </div>
            <div className="hi-oee-gauges">
              <div className="hi-oee-gauge-wrap">
                <GaugeArc value={data.oee} label="OEE GLOBAL" size={160} />
              </div>
              <div className="hi-oee-gauge-divider" />
              <div className="hi-oee-gauge-trio">
                <GaugeArc value={data.disponibilidade} label="DISPONIBILIDADE" size={120} />
                <GaugeArc value={data.performance}     label="PERFORMANCE"     size={120} />
                <GaugeArc value={data.qualidade}        label="QUALIDADE"       size={120} />
              </div>
            </div>
          </div>

          {/* Produção stats */}
          <div className="hi-kpi-row">
            <KPICard icon="✅" label="Produzido" value={data.produzido} unit="un"
              color="#16a34a" sub={`Meta: ${data.meta} un`} />
            <KPICard icon="❌" label="Rejeitado" value={data.reprovado} unit="un"
              color={data.reprovado > 0 ? "#dc2626" : "#16a34a"}
              sub={`FPY: ${data.produzido + data.reprovado > 0
                ? ((data.produzido / (data.produzido + data.reprovado)) * 100).toFixed(1)
                : "100"}%`} />
            <KPICard icon="📊" label="Total Processado"
              value={typeof data.produzido === "number" && typeof data.reprovado === "number"
                ? data.produzido + data.reprovado : "—"}
              unit="un" sub="Aprovadas + rejeitadas" />
          </div>

          {/* Gráficos */}
          <div className="hi-two-col">
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Produção Hora a Hora</span>
              </div>
              <HourlyChart data={data.producao_hora_a_hora} />
            </div>
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Pareto de Paradas</span>
                <span className="hi-section-sub">Top causas de inatividade</span>
              </div>
              <ParetoChart data={data.pareto_paradas} />
            </div>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <EmptyState icon="⚙️" text="Selecione uma linha, uma máquina e clique em Analisar" />
      )}
    </div>
  );
}

// ─── Tab 0: Por Turno (filtro primário) ──────────────────────────────────────

function TurnoTab() {
  const [linhas,         setLinhas]         = useState([]);
  const [selectedLinha,  setSelectedLinha]  = useState("");
  const [turnoOpts,      setTurnoOpts]      = useState([]);
  const [selectedTurno,  setSelectedTurno]  = useState(null);
  const [data,           setData]           = useState(null);
  const [loading,        setLoading]        = useState(false);
  const [error,          setError]          = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`).then((r) => r.json()).then(setLinhas).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedLinha) { setTurnoOpts([]); setSelectedTurno(null); setData(null); return; }
    fetch(`${API_BASE}/api/config/lines/${selectedLinha}/turnos/historico?limit=60`)
      .then((r) => r.json())
      .then((list) => { setTurnoOpts((list || []).filter((t) => t.status !== "agendado")); setSelectedTurno(null); setData(null); })
      .catch(() => setTurnoOpts([]));
  }, [selectedLinha]);

  function fmtLbl(t) {
    const dt = t.dt_real_inicio || t.dt_inicio;
    if (!dt) return t.nome;
    const d = new Date(dt);
    return `${t.nome} — ${d.toLocaleDateString("pt-BR")} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function pickTurno(t) {
    setSelectedTurno(t);
    if (!t) { setData(null); return; }
    const di = t.dt_real_inicio || t.dt_inicio;
    const df = t.dt_real_fim   || t.dt_fim;
    if (!di) return;
    const dfSafe = df || new Date().toISOString();
    setLoading(true); setData(null); setError(null);
    fetch(`${API_BASE}/api/historico/linha/${selectedLinha}?data_inicio=${encode(di)}&data_fim=${encode(dfSafe)}&turno_id=${t.id_ocorrencia}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  function gerarRelatorio() {
    if (!data || !selectedTurno) return;
    const di = selectedTurno.dt_real_inicio || selectedTurno.dt_inicio;
    const df = selectedTurno.dt_real_fim   || selectedTurno.dt_fim || new Date().toISOString();
    // wrap data in fabricaData-like shape for PDF
    const fab = { oee_global: data.oee, linhas: [{ ...data, nome: data.nome || "Linha", maquinas: data.maquinas || [], realizado: data.total_produzido, meta_total: data.meta_turno }] };
    exportarPDF(fab, null, di, df);
  }

  const aderencia = selectedTurno && selectedTurno.meta > 0
    ? Math.round(selectedTurno.produzido / selectedTurno.meta * 100) : null;

  return (
    <div className="hi-tab-content">
      {/* Seletor de linha + turno */}
      <div className="hi-turno-filter">
        <div className="hi-turno-step">
          <label className="hi-turno-step-lbl">Linha de Produção</label>
          <select className="hi-select hi-select-lg" value={selectedLinha}
            onChange={(e) => setSelectedLinha(e.target.value)}>
            <option value="">— Selecione a linha —</option>
            {linhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        </div>
        <div className="hi-turno-step">
          <label className="hi-turno-step-lbl">Turno</label>
          <select className="hi-select hi-select-lg"
            value={selectedTurno?.id_ocorrencia || ""}
            onChange={(e) => pickTurno(turnoOpts.find((t) => String(t.id_ocorrencia) === e.target.value) || null)}
            disabled={!selectedLinha || turnoOpts.length === 0}>
            <option value="">— Selecione o turno —</option>
            {turnoOpts.map((t) => <option key={t.id_ocorrencia} value={t.id_ocorrencia}>{fmtLbl(t)}</option>)}
          </select>
        </div>
        {data && (
          <button className="hi-buscar-btn hi-export-btn" onClick={gerarRelatorio}>
            Gerar PDF
          </button>
        )}
      </div>

      {/* Banner do turno selecionado */}
      {selectedTurno && (
        <div className="hi-turno-banner">
          <div className="hi-turno-banner-left">
            <span className="hi-turno-banner-nome">{selectedTurno.nome}</span>
            <span className={`hi-turno-banner-status hi-turno-banner-status--${selectedTurno.status}`}>
              {selectedTurno.status === "finalizado" ? "Finalizado" : selectedTurno.status === "em_andamento" ? "Em andamento" : selectedTurno.status}
            </span>
          </div>
          <div className="hi-turno-banner-times">
            <span>Início real: <strong>{selectedTurno.dt_real_inicio ? new Date(selectedTurno.dt_real_inicio).toLocaleString("pt-BR") : "—"}</strong></span>
            <span>Fim real: <strong>{selectedTurno.dt_real_fim ? new Date(selectedTurno.dt_real_fim).toLocaleString("pt-BR") : "Em curso"}</strong></span>
          </div>
          <div className="hi-turno-banner-kpis">
            <span>Meta: <strong>{selectedTurno.meta}</strong></span>
            <span>Produzido: <strong style={{ color: oeeColor(aderencia) }}>{selectedTurno.produzido}</strong></span>
            {aderencia !== null && (
              <span style={{ color: oeeColor(aderencia), fontWeight: 700 }}>Aderência: {aderencia}%</span>
            )}
          </div>
        </div>
      )}

      {loading && <div className="hi-loading"><Spinner /> Carregando dados do turno...</div>}
      {error && <div className="hi-error">{error}</div>}

      {data && !loading && (
        <>
          <div className="hi-kpi-row">
            <KPICard icon="⚡" label="OEE da Linha" value={data.oee ?? "—"} unit={data.oee !== null ? "%" : ""}
              color={oeeColor(data.oee)} sub={oeeLabel(data.oee)} />
            <KPICard icon="📦" label="Produção Total" value={(data.total_produzido || 0).toLocaleString("pt-BR")}
              unit="un" color="#3b82f6" sub={`${data.maquinas?.length || 0} máquinas`} />
            <KPICard icon="🔍" label="Taxa de Rejeição" value={data.taxa_rejeicao ?? "—"}
              unit={data.taxa_rejeicao != null ? "%" : ""} color={data.taxa_rejeicao > 10 ? "#dc2626" : "#16a34a"}
              sub={`${data.total_reprovado ?? 0} rejeitadas`} />
          </div>

          {/* OEE breakdown por máquina */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">OEE por Máquina — Turno</span>
              <span className="hi-section-sub">Disponibilidade × Performance × Qualidade</span>
            </div>
            <div className="hi-machine-grid">
              {data.maquinas?.map((m) => <MachineCard key={m.id} m={m} />)}
            </div>
          </div>

          {/* Breakdown OEE chart */}
          {data.maquinas?.length > 1 && (
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">OEE Breakdown</span>
              </div>
              <MaquinasOEEChart maquinas={data.maquinas} />
            </div>
          )}

          {/* Produção hora a hora */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">Produção Hora a Hora</span>
              <span className="hi-section-sub">Dentro do turno selecionado</span>
            </div>
            <HourlyChart data={data.producao_hora_a_hora} />
          </div>

          {/* Turnos + Ordens */}
          {data.ordens?.length > 0 && (
            <div className="hi-section">
              <div className="hi-section-header"><span className="hi-section-title">Ordens de Produção no Turno</span></div>
              <OrdensTable ordens={data.ordens} />
            </div>
          )}

          {/* Pareto de paradas */}
          {data.pareto_paradas?.length > 0 && (
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Pareto de Paradas</span>
                <span className="hi-section-sub">Principais causas de inatividade no turno</span>
              </div>
              <ParetoChart data={data.pareto_paradas} />
            </div>
          )}
        </>
      )}

      {!selectedTurno && !loading && (
        <EmptyState icon="🔄" text="Selecione uma linha e um turno para ver o dashboard completo" />
      )}
    </div>
  );
}

// ─── Export PDF (via window.print) ───────────────────────────────────────────

function exportarPDF(fabricaData, funil, inicio, fim) {
  if (!fabricaData) return;
  const fmtDt = (s) => (s ? s.replace("T", " ") : "");
  const n = (v) => (v ?? 0).toLocaleString("pt-BR");
  const pct = (v) => v != null ? `${Number(v).toFixed(1)}%` : "—";
  const totalProd = fabricaData.linhas.reduce((s, l) => s + (l.realizado || 0), 0);
  const totalMeta = fabricaData.linhas.reduce((s, l) => s + (l.meta_total || 0), 0);
  const allMaq    = fabricaData.linhas.flatMap((l) => l.maquinas || []);
  const totalRej  = allMaq.reduce((s, m) => s + (m.reprovado || 0), 0);
  const taxaRej   = (totalProd + totalRej) > 0 ? +((totalRej / (totalProd + totalRej)) * 100).toFixed(2) : 0;
  const ader      = totalMeta > 0 ? +((totalProd / totalMeta) * 100).toFixed(1) : null;
  const gerado    = new Date().toLocaleString("pt-BR");

  function cls(v) { const x = Number(v); if (isNaN(x)) return ""; return x >= 75 ? "green" : x >= 50 ? "orange" : "red"; }

  const linhasRows = fabricaData.linhas.map((l) => {
    const a = l.meta_total > 0 ? +((l.realizado / l.meta_total) * 100).toFixed(1) : null;
    return `<tr><td>${l.nome}</td><td class="c ${cls(l.oee)}">${pct(l.oee)}</td><td class="r">${n(l.realizado)}</td><td class="r">${n(l.meta_total)}</td><td class="c ${cls(a)}">${a != null ? a + "%" : "—"}</td><td class="c">${l.maquinas?.length || 0}</td></tr>`;
  }).join("");
  const maqRows = fabricaData.linhas.flatMap((l) =>
    (l.maquinas || []).map((m) => `<tr><td>${l.nome}</td><td>${m.nome}</td><td class="c ${cls(m.oee)}">${pct(m.oee)}</td><td class="c ${cls(m.disponibilidade)}">${pct(m.disponibilidade)}</td><td class="c ${cls(m.performance)}">${pct(m.performance)}</td><td class="c ${cls(m.qualidade)}">${pct(m.qualidade)}</td><td class="r">${n(m.produzido)}</td><td class="r">${n(m.meta)}</td><td class="r ${(m.reprovado||0)>0?"red":""}">${n(m.reprovado)}</td><td>${m.status||"—"}</td></tr>`)
  ).join("");
  const funilHTML = funil ? `<div class="st">Ordens de Producao</div><table style="width:240px"><thead><tr><th>Status</th><th>OPs</th><th>Pecas</th></tr></thead><tbody><tr><td>Na Fila</td><td class="c">${funil.fila?.qty||0}</td><td class="r">${n(funil.fila?.pecas)}</td></tr><tr><td>Em Producao</td><td class="c">${funil.em_producao?.qty||0}</td><td class="r">${n(funil.em_producao?.pecas)}</td></tr><tr><td class="green">Finalizados</td><td class="c green">${funil.finalizado?.qty||0}</td><td class="r green">${n(funil.finalizado?.pecas)}</td></tr><tr><td class="red">Cancelados</td><td class="c red">${funil.cancelado?.qty||0}</td><td class="r red">${n(funil.cancelado?.pecas)}</td></tr></tbody></table>` : "";

  const kpis = [
    { label: "OEE Global", val: fabricaData.oee_global != null ? fabricaData.oee_global+"%" : "—", ac: cls(fabricaData.oee_global)||"blue" },
    { label: "Producao Total", val: n(totalProd)+" un", ac: "blue" },
    { label: "Meta Total", val: n(totalMeta)+" un", ac: "gray" },
    { label: "Aderencia Meta", val: ader != null ? ader+"%" : "—", ac: cls(ader)||"blue" },
    { label: "Rejeitado", val: n(totalRej)+" un", ac: taxaRej>10?"red":"green" },
    { label: "Taxa Rejeicao", val: taxaRej+"%", ac: taxaRej>10?"red":"green" },
  ];
  const kpiHTML = kpis.map((k) => `<div class="kpi kpi-${k.ac}"><div class="kl">${k.label}</div><div class="kv">${k.val}</div></div>`).join("");

  const html = `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Relatorio de Producao</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;font-size:11px;color:#111}
@page{size:A4 landscape;margin:12mm 14mm}
@media print{.np{display:none!important}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.hdr{background:#1D4ED8;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;border-radius:6px;margin-bottom:16px}
.hdr h1{font-size:16px;font-weight:700}.hdr-r{text-align:right;font-size:9px;line-height:1.8;opacity:.9}
.kgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:16px}
.kpi{background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:10px 8px;text-align:center;position:relative}
.kpi::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;border-radius:6px 6px 0 0;background:var(--ac)}
.kpi-blue{--ac:#1D4ED8}.kpi-green{--ac:#16A34A}.kpi-orange{--ac:#D97706}.kpi-red{--ac:#DC2626}.kpi-gray{--ac:#6B7280}
.kl{font-size:8px;color:#6b7280;text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px}
.kv{font-size:17px;font-weight:700;color:var(--ac)}
.st{font-size:12px;font-weight:700;border-left:3px solid #1D4ED8;padding-left:8px;margin:14px 0 7px}
table{width:100%;border-collapse:collapse;margin-bottom:14px;font-size:10px}
th{background:#1D4ED8;color:#fff;padding:6px 8px;font-weight:700;white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid #e5e7eb}tr:nth-child(even) td{background:#f8fafc}
.c{text-align:center}.r{text-align:right}
.green{color:#16A34A;font-weight:700}.orange{color:#D97706;font-weight:700}.red{color:#DC2626;font-weight:700}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.pb{page-break-before:always;padding-top:2px}
.ftr{margin-top:16px;padding-top:8px;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between;font-size:8px;color:#9ca3af}
.btn{background:#1D4ED8;color:#fff;border:none;padding:8px 18px;font-size:13px;border-radius:5px;cursor:pointer;margin-bottom:14px}
</style></head><body>
<button class="btn np" onclick="window.print()">Imprimir / Salvar PDF</button>
<div class="hdr"><div><h1>Relatorio de Producao</h1><div style="font-size:9px;opacity:.85;margin-top:3px">Resumo Executivo — Visao Geral da Fabrica</div></div><div class="hdr-r"><div>Periodo: <strong>${fmtDt(inicio)} &rarr; ${fmtDt(fim)}</strong></div><div>Gerado em: ${gerado}</div><div>${fabricaData.linhas.length} linhas &middot; ${allMaq.length} maquinas</div></div></div>
<div class="kgrid">${kpiHTML}</div>
<div class="two">
<div><div class="st">Desempenho por Linha</div><table><thead><tr><th>Linha</th><th>OEE</th><th>Produzido</th><th>Meta</th><th>Aderencia</th><th>Maquinas</th></tr></thead><tbody>${linhasRows}</tbody></table></div>
<div>${funilHTML}</div>
</div>
<div class="ftr"><span>PCP Analytics — Relatorio Confidencial</span><span>Pagina 1 de 2</span></div>
<div class="pb">
<div class="hdr"><div><h1>Relatorio de Producao</h1><div style="font-size:9px;opacity:.85;margin-top:3px">Drill-down por Maquina</div></div><div class="hdr-r"><div>Periodo: <strong>${fmtDt(inicio)} &rarr; ${fmtDt(fim)}</strong></div><div>Gerado em: ${gerado}</div></div></div>
<div class="st">Detalhamento por Maquina</div>
<table><thead><tr><th>Linha</th><th>Maquina</th><th>OEE</th><th>Disponib.</th><th>Perf.</th><th>Qualid.</th><th>Produzido</th><th>Meta</th><th>Rejeitado</th><th>Status</th></tr></thead><tbody>${maqRows}</tbody></table>
<div class="ftr"><span>PCP Analytics — Relatorio Confidencial</span><span>Pagina 2 de 2</span></div>
</div>
</body></html>`;

  const w = window.open("", "_blank");
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 500);
}

// ─── Atalhos de período ───────────────────────────────────────────────────────

const SHORTCUTS = [
  { label: "Hoje", range: () => { const s = new Date(); s.setHours(0,0,0,0); return [toLocalDT(s), toLocalDT(new Date())]; } },
  { label: "Ontem", range: () => { const s = new Date(); s.setDate(s.getDate()-1); s.setHours(0,0,0,0); const e = new Date(); e.setDate(e.getDate()-1); e.setHours(23,59,0,0); return [toLocalDT(s), toLocalDT(e)]; } },
  { label: "Últ. 8h", range: () => { const e = new Date(); return [toLocalDT(new Date(e - 8*3600e3)), toLocalDT(e)]; } },
  { label: "Últ. 24h", range: () => { const e = new Date(); return [toLocalDT(new Date(e - 24*3600e3)), toLocalDT(e)]; } },
  { label: "7 dias", range: () => { const e = new Date(); const s = new Date(e - 7*24*3600e3); s.setHours(0,0,0,0); return [toLocalDT(s), toLocalDT(e)]; } },
];

const TABS = [
  { key: "turno",   label: "🔄 Por Turno",       sub: "Principal" },
  { key: "fabrica", label: "🏭 Visão Geral",      sub: "Fábrica" },
  { key: "linha",   label: "🔧 Por Linha",        sub: "Análise" },
  { key: "maquina", label: "⚙️ Por Máquina",     sub: "Drill-down" },
];

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Historico() {
  const now        = new Date();
  const startOfDay = new Date(now); startOfDay.setHours(0,0,0,0);

  const [inicio,        setInicio]        = useState(toLocalDT(startOfDay));
  const [fim,           setFim]           = useState(toLocalDT(now));
  const [activeShortcut, setActiveShortcut] = useState("Hoje");
  const [activeTab,     setActiveTab]     = useState("turno");

  const [fabricaData, setFabricaData] = useState(null);
  const [funil,       setFunil]       = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);

  function applyShortcut(s) {
    const [i, f] = s.range();
    setInicio(i); setFim(f); setActiveShortcut(s.label);
  }

  function buscar() {
    setLoading(true); setError(null); setFabricaData(null); setFunil(null);
    Promise.all([
      fetch(`${API_BASE}/api/historico?data_inicio=${encode(inicio)}&data_fim=${encode(fim)}`).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      fetch(`${API_BASE}/api/historico/ordens?data_inicio=${encode(inicio)}&data_fim=${encode(fim)}`).then((r) => r.ok ? r.json() : null),
    ])
      .then(([fab, fun]) => { setFabricaData(fab); setFunil(fun); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  return (
    <div className="hi-root">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="hi-filter-card">
        <div className="hi-filter-top">
          <div className="hi-filter-title-block">
            <h1 className="hi-page-title">Analytics de Produção</h1>
            <p className="hi-page-sub">Indicadores de desempenho por período, linha e máquina</p>
          </div>
          <div className="hi-filter-shortcuts">
            {SHORTCUTS.map((s) => (
              <button key={s.label}
                className={`hi-shortcut${activeShortcut === s.label ? " hi-shortcut--active" : ""}`}
                onClick={() => applyShortcut(s)}
              >{s.label}</button>
            ))}
          </div>
        </div>
        <div className="hi-filter-row">
          <div className="hi-filter-field">
            <label className="hi-filter-label">Início</label>
            <input type="datetime-local" className="hi-filter-input" value={inicio}
              onChange={(e) => { setInicio(e.target.value); setActiveShortcut(null); }} />
          </div>
          <div className="hi-filter-sep">→</div>
          <div className="hi-filter-field">
            <label className="hi-filter-label">Fim</label>
            <input type="datetime-local" className="hi-filter-input" value={fim}
              onChange={(e) => { setFim(e.target.value); setActiveShortcut(null); }} />
          </div>
          <button className="hi-buscar-btn" onClick={buscar} disabled={loading}>
            {loading ? <><Spinner size={14} /> Buscando...</> : "Buscar Dados"}
          </button>
          {fabricaData && (
            <button className="hi-buscar-btn hi-export-btn"
              onClick={() => exportarPDF(fabricaData, funil, inicio, fim)}>
              ⬇ Gerar PDF
            </button>
          )}
        </div>
      </div>

      {error && <div className="hi-error">⚠ {error}</div>}

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="hi-tabs">
        {TABS.map((t) => (
          <button key={t.key}
            className={`hi-tab${activeTab === t.key ? " hi-tab--active" : ""}`}
            onClick={() => setActiveTab(t.key)}
          >
            <span className="hi-tab-label">{t.label}</span>
            <span className="hi-tab-sub">{t.sub}</span>
          </button>
        ))}
      </div>

      {/* ── Tab Content ──────────────────────────────────────────────────── */}
      {loading && activeTab !== "turno" ? (
        <div className="hi-loading"><Spinner /> Carregando dados da fábrica...</div>
      ) : (
        <>
          {activeTab === "turno"   && <TurnoTab />}
          {activeTab === "fabrica" && <FabricaTab data={fabricaData} funil={funil} />}
          {activeTab === "linha"   && <LinhaTab   linhas={fabricaData?.linhas} inicio={inicio} fim={fim} />}
          {activeTab === "maquina" && <MaquinaTab linhas={fabricaData?.linhas} inicio={inicio} fim={fim} />}
        </>
      )}

    </div>
  );
}
