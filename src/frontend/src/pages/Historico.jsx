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

function LinhaTab({ linhas, inicio, fim, defaultLinhaId }) {
  const [selectedId, setSelectedId]     = useState(() => defaultLinhaId ? String(defaultLinhaId) : "");
  const [turnoOpts, setTurnoOpts]       = useState([]);
  const [selectedTurno, setSelectedTurno] = useState("");
  const [data, setData]                 = useState(null);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);

  // Sincroniza com a linha padrão do header
  useEffect(() => {
    if (defaultLinhaId && !selectedId) setSelectedId(String(defaultLinhaId));
  }, [defaultLinhaId]);

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

// ─── Tab 0: Por Turno (driven by header selection) ──────────────────────────

function TurnoTab({ selectedTurno, selectedLinhaId }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!selectedTurno || !selectedLinhaId) { setData(null); return; }
    const di = selectedTurno.dt_real_inicio || selectedTurno.dt_inicio;
    const df = selectedTurno.dt_real_fim   || selectedTurno.dt_fim || new Date().toISOString();
    if (!di) { setData(null); return; }
    setLoading(true); setData(null); setError(null);
    fetch(`${API_BASE}/api/historico/linha/${selectedLinhaId}?data_inicio=${encode(di)}&data_fim=${encode(df)}&turno_id=${selectedTurno.id_ocorrencia}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d)  => { setData(d);   setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }, [selectedTurno?.id_ocorrencia, selectedLinhaId]);

  function gerarPDF() {
    if (!data || !selectedTurno) return;
    const di  = selectedTurno.dt_real_inicio || selectedTurno.dt_inicio;
    const df  = selectedTurno.dt_real_fim   || selectedTurno.dt_fim || new Date().toISOString();
    const fab = {
      oee_global: data.oee,
      linhas: [{ ...data, nome: data.nome || "Linha", maquinas: data.maquinas || [],
        realizado: data.total_produzido, meta_total: data.meta_turno }],
    };
    exportarPDF(fab, null, di, df, selectedTurno);
  }

  async function gerarExcel() {
    if (!data || !selectedTurno) return;
    const di  = selectedTurno.dt_real_inicio || selectedTurno.dt_inicio;
    const df  = selectedTurno.dt_real_fim   || selectedTurno.dt_fim || new Date().toISOString();
    const fab = {
      oee_global: data.oee,
      linhas: [{ ...data, nome: data.nome || "Linha", maquinas: data.maquinas || [],
        realizado: data.total_produzido, meta_total: data.meta_turno }],
    };
    await exportarExcel(fab, null, di, df, selectedTurno);
  }

  if (!selectedTurno || !selectedLinhaId) {
    return (
      <div className="hi-tab-content">
        <EmptyState icon="🔄" text="Selecione uma linha e um turno no painel acima para carregar os detalhes" />
      </div>
    );
  }

  const aderencia = selectedTurno.meta > 0
    ? Math.round((selectedTurno.produzido / selectedTurno.meta) * 100) : null;

  return (
    <div className="hi-tab-content">
      {loading && <div className="hi-loading"><Spinner /> Carregando dados do turno...</div>}
      {error   && <div className="hi-error">{error}</div>}

      {data && !loading && (
        <>
          {/* KPIs do turno */}
          <div className="hi-kpi-row">
            <KPICard icon="⚡" label="OEE da Linha"
              value={data.oee ?? "—"} unit={data.oee !== null ? "%" : ""}
              color={oeeColor(data.oee)} sub={oeeLabel(data.oee)} />
            <KPICard icon="📦" label="Produção Total"
              value={(data.total_produzido || 0).toLocaleString("pt-BR")}
              unit="un" color="#3b82f6" sub={`${data.maquinas?.length || 0} máquinas na linha`} />
            <KPICard icon="🔍" label="Taxa de Rejeição"
              value={data.taxa_rejeicao ?? "—"} unit={data.taxa_rejeicao != null ? "%" : ""}
              color={data.taxa_rejeicao > 10 ? "#dc2626" : "#16a34a"}
              sub={`${data.total_reprovado ?? 0} rejeitadas`} />
            {aderencia !== null && (
              <KPICard icon="🎯" label="Aderência à Meta"
                value={aderencia} unit="%"
                color={oeeColor(aderencia)}
                sub={`${selectedTurno.produzido} / ${selectedTurno.meta} un`} />
            )}
          </div>

          {/* OEE por máquina */}
          <div className="hi-section">
            <div className="hi-section-header">
              <span className="hi-section-title">OEE por Máquina</span>
              <span className="hi-section-sub">Disponibilidade × Performance × Qualidade</span>
            </div>
            <div className="hi-machine-grid">
              {data.maquinas?.map((m) => <MachineCard key={m.id} m={m} />)}
            </div>
          </div>

          {/* OEE breakdown chart */}
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
              <span className="hi-section-sub">Dentro do turno</span>
            </div>
            <HourlyChart data={data.producao_hora_a_hora} />
          </div>

          {/* Ordens */}
          {data.ordens?.length > 0 && (
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Ordens de Produção no Turno</span>
              </div>
              <OrdensTable ordens={data.ordens} />
            </div>
          )}

          {/* Pareto */}
          {data.pareto_paradas?.length > 0 && (
            <div className="hi-section">
              <div className="hi-section-header">
                <span className="hi-section-title">Pareto de Paradas</span>
                <span className="hi-section-sub">Principais causas de inatividade no turno</span>
              </div>
              <ParetoChart data={data.pareto_paradas} />
            </div>
          )}

          {/* Export buttons do turno */}
          <div className="hi-turno-export-row">
            <button className="hi-buscar-btn hi-export-btn hi-export-btn--pdf" onClick={gerarPDF}>
              📄 PDF do Turno
            </button>
            <TurnoExcelBtn data={data} turno={selectedTurno} />
          </div>
        </>
      )}
    </div>
  );
}

function TurnoExcelBtn({ data, turno }) {
  const [exp, setExp] = useState(false);
  async function go() {
    setExp(true);
    try { await gerarExcelTurno(data, turno); }
    finally { setExp(false); }
  }
  return (
    <button className="hi-buscar-btn hi-export-btn hi-export-btn--excel" onClick={go} disabled={exp}>
      {exp ? <><Spinner size={14} /> Excel...</> : "📊 Excel do Turno"}
    </button>
  );
}

async function gerarExcelTurno(data, turno) {
  const di  = turno.dt_real_inicio || turno.dt_inicio;
  const df  = turno.dt_real_fim   || turno.dt_fim || new Date().toISOString();
  const fab = {
    oee_global: data.oee,
    linhas: [{ ...data, nome: data.nome || "Linha", maquinas: data.maquinas || [],
      realizado: data.total_produzido, meta_total: data.meta_turno }],
  };
  await exportarExcel(fab, null, di, df, turno);
}


// ─── PDF helpers ─────────────────────────────────────────────────────────────

function _pdfSVGGauge(pct, size = 90) {
  const r = size / 2 - 8;
  const cx = size / 2, cy = size / 2;
  const angle = Math.PI * 1.5; // 270° arc
  const startAngle = Math.PI * 0.75; // starts at 7-o'clock
  const sweep = angle * Math.min(1, Math.max(0, pct / 100));
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(startAngle + sweep);
  const y2 = cy + r * Math.sin(startAngle + sweep);
  const color = pct >= 85 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
  const largeArc = sweep > Math.PI ? 1 : 0;
  const bg_x2 = cx + r * Math.cos(startAngle + angle);
  const bg_y2 = cy + r * Math.sin(startAngle + angle);
  return (
    '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '">' +
    '<path d="M ' + x1.toFixed(2) + ' ' + y1.toFixed(2) +
          ' A ' + r + ' ' + r + ' 0 1 1 ' + bg_x2.toFixed(2) + ' ' + bg_y2.toFixed(2) + '"' +
          ' fill="none" stroke="#e5e7eb" stroke-width="8" stroke-linecap="round"/>' +
    (sweep > 0.01 ?
    '<path d="M ' + x1.toFixed(2) + ' ' + y1.toFixed(2) +
          ' A ' + r + ' ' + r + ' 0 ' + largeArc + ' 1 ' + x2.toFixed(2) + ' ' + y2.toFixed(2) + '"' +
          ' fill="none" stroke="' + color + '" stroke-width="8" stroke-linecap="round"/>' : '') +
    '<text x="' + cx + '" y="' + (cy + 5) + '" text-anchor="middle" font-size="16" font-weight="bold" fill="' + color + '">' + pct.toFixed(1) + '%</text>' +
    '</svg>'
  );
}

function _pdfMiniBar(pct, width = 120) {
  const color = pct >= 85 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
  const fill = Math.min(100, Math.max(0, pct));
  return (
    '<svg width="' + width + '" height="14" viewBox="0 0 ' + width + ' 14">' +
    '<rect x="0" y="3" width="' + width + '" height="8" rx="4" fill="#e5e7eb"/>' +
    '<rect x="0" y="3" width="' + (width * fill / 100).toFixed(1) + '" height="8" rx="4" fill="' + color + '"/>' +
    '</svg>'
  );
}

function _categorizarMotivo(motivo) {
  const m = (motivo || '').toLowerCase();
  if (m.includes('manuten') || m.includes('manutentor'))
    return { cat: 'Manutenção',   color: '#ef4444', argb: 'FFEF4444', bg: '#fef2f2', bgArgb: 'FFFEF2F2' };
  if (m.includes('limpeza') || m.includes('setup') || m.includes('troca'))
    return { cat: 'Setup/Limpeza', color: '#f59e0b', argb: 'FFF59E0B', bg: '#fffbeb', bgArgb: 'FFFFBEB' };
  if (m.includes('aguardando') || m.includes('operador') || m.includes('material') || m.includes('insumo'))
    return { cat: 'Aguardando',   color: '#3b82f6', argb: 'FF3B82F6', bg: '#eff6ff', bgArgb: 'FFEFF6FF' };
  if (m === 'sem motivo' || m.startsWith('motivo 0'))
    return { cat: 'Sem Motivo',   color: '#94a3b8', argb: 'FF94A3B8', bg: '#f8fafc', bgArgb: 'FFF8FAFC' };
  return   { cat: 'Operacional',  color: '#8b5cf6', argb: 'FF8B5CF6', bg: '#faf5ff', bgArgb: 'FFFAF5FF' };
}

function exportarPDF(fabricaData, funil, inicio, fim, turno) {
  const fmt  = (v, d = 1) => v == null ? '—' : Number(v).toFixed(d);
  const pct  = (v) => v == null ? '—' : Number(v).toFixed(1) + '%';
  const fmtDt = (s) => { try { return new Date(s).toLocaleString('pt-BR'); } catch { return s || '—'; } };
  const fmtMin = (m) => {
    const h = Math.floor(m / 60); const mn = Math.round(m % 60);
    return h > 0 ? (h + 'h ' + mn + 'min') : (mn + 'min');
  };
  const oeeColor = (v) => v >= 85 ? '#16a34a' : v >= 60 ? '#d97706' : '#dc2626';
  const linhas = fabricaData?.linhas || [];
  const oeeGlobal = Number(fabricaData?.oee_global || 0);

  const turnoNome = turno ? (turno.nome || ('Turno #' + turno.id_ocorrencia)) : null;
  const periodoStr = turnoNome
    ? (turnoNome + ' &nbsp;|&nbsp; ' + fmtDt(inicio) + ' → ' + fmtDt(fim))
    : (fmtDt(inicio) + ' → ' + fmtDt(fim));

  // ── Build linha rows ──────────────────────────────────────────────────────
  const linhaRows = linhas.map((l, i) => {
    const bg = i % 2 === 0 ? '#f8fafc' : '#ffffff';
    const oee = Number(l.oee || 0);
    return (
      '<tr style="background:' + bg + '">' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:500">' + (l.nome || 'Linha ' + l.id_linha) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center;color:' + oeeColor(oee) + ';font-weight:700">' + pct(l.oee) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + pct(l.disponibilidade) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + pct(l.performance) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + pct(l.qualidade) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right">' + fmt(l.realizado, 0) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right">' + fmt(l.meta_total, 0) + '</td>' +
      '</tr>'
    );
  }).join('');

  // ── Ordens — usa lista real das linhas; funil (sumário) como fallback ───────
  const allOrdens = linhas.flatMap(l => l.ordens || []);
  // Deriva resumo do funil a partir das ordens reais quando funil não está disponível
  const funilEfetivo = funil || (allOrdens.length > 0 ? {
    total_ordens:  allOrdens.length,
    concluidas:    allOrdens.filter(o => o.status === 'finalizado'   || o.conclusao >= 100).length,
    iniciadas:     allOrdens.filter(o => o.status === 'em_producao').length,
    nao_iniciadas: allOrdens.filter(o => o.status === 'fila').length,
    atrasadas:     0,
  } : null);

  const funilRows = funilEfetivo ? [
    ['Total de Ordens',   funilEfetivo.total_ordens  || 0, '#3b82f6'],
    ['Em Produção',       funilEfetivo.iniciadas     || 0, '#8b5cf6'],
    ['Concluídas',        funilEfetivo.concluidas    || 0, '#22c55e'],
    ['Não Iniciadas',     funilEfetivo.nao_iniciadas || 0, '#f59e0b'],
    ['Atrasadas',         funilEfetivo.atrasadas     || 0, '#ef4444'],
  ].map(([label, val, color], i) => {
    const bg = i % 2 === 0 ? '#f8fafc' : '#ffffff';
    const max = funilEfetivo.total_ordens || 1;
    return (
      '<tr style="background:' + bg + '">' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + label + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center;color:' + color + ';font-weight:700">' + val + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + _pdfMiniBar(val / max * 100, 100) + '</td>' +
      '</tr>'
    );
  }).join('') : '<tr><td colspan="3" style="padding:8px;color:#9ca3af;text-align:center">Nenhuma ordem encontrada</td></tr>';

  // Linhas detalhadas das ordens (para a tabela da pág. 2)
  const statusColor = (s) => s === 'finalizado' ? '#16a34a' : s === 'em_producao' ? '#2563eb' : s === 'cancelada' ? '#dc2626' : '#92400e';
  const statusLabel = (s) => s === 'finalizado' ? 'Concluída' : s === 'em_producao' ? 'Em Produção' : s === 'fila' ? 'Na Fila' : s === 'cancelada' ? 'Cancelada' : s || '—';
  const ordensRows = allOrdens.length > 0
    ? allOrdens.map((o, i) => {
        const bg = i % 2 === 0 ? '#f8fafc' : '#ffffff';
        const sc = statusColor(o.status);
        const conc = o.conclusao ?? (o.quantidade > 0 ? Math.round(o.produzido / o.quantidade * 100) : 0);
        return (
          '<tr style="background:' + bg + '">' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0;font-weight:600">' + (o.numero || '—') + '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0">' + (o.peca || '—') + '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0;text-align:center">' + (o.quantidade || 0).toLocaleString('pt-BR') + '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0;text-align:center">' + (o.produzido || 0).toLocaleString('pt-BR') + '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0;text-align:center;color:#dc2626">' + (o.refugo || 0) + '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0;text-align:center">' +
            '<span style="background:' + sc + '1a;color:' + sc + ';padding:1px 7px;border-radius:10px;font-size:9.5px;font-weight:600">' + statusLabel(o.status) + '</span>' +
          '</td>' +
          '<td style="padding:5px 7px;border-bottom:1px solid #e2e8f0">' + _pdfMiniBar(conc, 80) + '</td>' +
          '</tr>'
        );
      }).join('')
    : '<tr><td colspan="7" style="padding:8px;color:#9ca3af;text-align:center">Nenhuma ordem no período</td></tr>';

  // ── Pareto consolidado (todas as linhas) ──────────────────────────────────
  const paradaAgg = {};
  linhas.forEach(l => {
    (l.pareto_paradas || []).forEach(p => {
      paradaAgg[p.motivo] = (paradaAgg[p.motivo] || 0) + p.minutos;
    });
  });
  const totalParadaMin = Object.values(paradaAgg).reduce((s, v) => s + v, 0);
  const paradaSorted = Object.entries(paradaAgg).sort((a, b) => b[1] - a[1]).slice(0, 10);

  // Pareto por categoria
  const catAgg = {};
  paradaSorted.forEach(([mot, mins]) => {
    const c = _categorizarMotivo(mot);
    catAgg[c.cat] = catAgg[c.cat] || { color: c.color, bg: c.bg, mins: 0, count: 0 };
    catAgg[c.cat].mins  += mins;
    catAgg[c.cat].count += 1;
  });
  const catSorted = Object.entries(catAgg).sort((a, b) => b[1].mins - a[1].mins);

  const catRows = catSorted.map(([cat, data], i) => {
    const bg = i % 2 === 0 ? '#f8fafc' : '#ffffff';
    const pctCat = totalParadaMin > 0 ? (data.mins / totalParadaMin * 100) : 0;
    return (
      '<tr style="background:' + bg + '">' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' +
        '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + data.color + ';margin-right:6px;vertical-align:middle"></span>' + cat +
      '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center;color:' + data.color + ';font-weight:700">' + fmtMin(data.mins) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + pctCat.toFixed(1) + '%</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + _pdfMiniBar(pctCat, 90) + '</td>' +
      '</tr>'
    );
  }).join('');

  const paradaRows = paradaSorted.map(([mot, mins], i) => {
    const bg = i % 2 === 0 ? '#f8fafc' : '#ffffff';
    const c = _categorizarMotivo(mot);
    const pctMot = totalParadaMin > 0 ? (mins / totalParadaMin * 100) : 0;
    return (
      '<tr style="background:' + bg + '">' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:500">' + mot + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' +
        '<span style="background:' + c.bg + ';color:' + c.color + ';padding:1px 6px;border-radius:10px;font-size:9px;font-weight:600">' + c.cat + '</span>' +
      '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center;color:' + c.color + ';font-weight:700">' + fmtMin(mins) + '</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + pctMot.toFixed(1) + '%</td>' +
      '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + _pdfMiniBar(pctMot, 90) + '</td>' +
      '</tr>'
    );
  }).join('') || '<tr><td colspan="5" style="padding:8px;color:#9ca3af;text-align:center">Nenhuma parada registrada neste período</td></tr>';

  // ── Pareto por máquina ────────────────────────────────────────────────────
  const maqParadaRows = linhas.flatMap(l =>
    (l.maquinas || []).filter(m => m.pareto_paradas?.length > 0).flatMap((m, mi) => {
      const total = m.pareto_paradas.reduce((s, p) => s + p.minutos, 0);
      return m.pareto_paradas.slice(0, 5).map((p, pi) => {
        const bg = mi % 2 === 0 ? '#f8fafc' : '#ffffff';
        const c  = _categorizarMotivo(p.motivo);
        const bar = _pdfMiniBar(p.percentual, 70);
        return (
          '<tr style="background:' + bg + '">' +
          (pi === 0
            ? '<td rowspan="' + Math.min(5, m.pareto_paradas.length) + '" style="padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:600;vertical-align:top">' + (m.nome || 'Máquina ' + m.id) + '</td>'
            : '') +
          '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + p.motivo + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' +
            '<span style="background:' + c.bg + ';color:' + c.color + ';padding:1px 6px;border-radius:10px;font-size:9px;font-weight:600">' + c.cat + '</span>' +
          '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center;color:' + c.color + ';font-weight:600">' + fmtMin(p.minutos) + '</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">' + p.percentual.toFixed(1) + '%</td>' +
          '<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">' + bar + '</td>' +
          '</tr>'
        );
      });
    })
  ).join('') || '<tr><td colspan="6" style="padding:8px;color:#9ca3af;text-align:center">Sem dados por máquina</td></tr>';

  const temParadas = paradaSorted.length > 0;

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<title>Relatório PCP</title>
<style>
  @page { size: A4 landscape; margin: 12mm; }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; }
  body { background: #fff; color: #1e293b; font-size: 11px; }
  .page { width: 100%; page-break-after: always; }
  .page:last-child { page-break-after: avoid; }
  h1 { font-size: 20px; font-weight: 800; }
  h2 { font-size: 13px; font-weight: 700; margin-bottom: 8px; color: #1e293b; }
  table { width: 100%; border-collapse: collapse; font-size: 10.5px; }
  th { background: #1e3a5f; color: #fff; padding: 6px 8px; text-align: left; font-weight: 600; }
  th:not(:first-child) { text-align: center; }
  .section-badge { display:inline-block;background:#1e3a5f;color:#fff;font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px }
</style>
</head>
<body>

<!-- PAGE 1: KPIs + Linhas -->
<div class="page">
  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:16px 20px;border-radius:8px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <h1>Relatório de Produção</h1>
      <div style="font-size:11px;opacity:.85;margin-top:4px">${periodoStr}</div>
    </div>
    <div style="text-align:right;font-size:10px;opacity:.75">
      Gerado em: ${new Date().toLocaleString('pt-BR')}<br/>Sistema PCP — MES
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:16px">
    <div style="flex:1;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px;text-align:center">
      ${_pdfSVGGauge(oeeGlobal, 80)}
      <div style="font-size:10px;color:#16a34a;font-weight:600;margin-top:4px">OEE Global</div>
    </div>
    <div style="flex:1;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:#1d4ed8">${linhas.length}</div>
      <div style="font-size:10px;color:#1d4ed8;font-weight:600;margin-top:4px">Linhas Ativas</div>
    </div>
    <div style="flex:1;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:#c2410c">${funilEfetivo?.total_ordens || allOrdens.length || 0}</div>
      <div style="font-size:10px;color:#c2410c;font-weight:600;margin-top:4px">Total de Ordens</div>
    </div>
    <div style="flex:1;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:#16a34a">${funilEfetivo?.concluidas || 0}</div>
      <div style="font-size:10px;color:#16a34a;font-weight:600;margin-top:4px">Ordens Concluídas</div>
    </div>
    <div style="flex:1;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:#dc2626">${funilEfetivo?.atrasadas || 0}</div>
      <div style="font-size:10px;color:#dc2626;font-weight:600;margin-top:4px">Ordens Atrasadas</div>
    </div>
    <div style="flex:1;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:#7c3aed">${temParadas ? fmtMin(totalParadaMin) : '—'}</div>
      <div style="font-size:10px;color:#7c3aed;font-weight:600;margin-top:4px">Tempo Total Parado</div>
    </div>
  </div>

  <h2>Performance por Linha</h2>
  <table>
    <thead><tr><th>Linha</th><th>OEE</th><th>Disponib.</th><th>Performance</th><th>Qualidade</th><th>Produzido</th><th>Meta</th></tr></thead>
    <tbody>${linhaRows || '<tr><td colspan="7" style="padding:8px;color:#9ca3af">Sem dados de linhas</td></tr>'}</tbody>
  </table>
</div>

<!-- PAGE 2: Funil + OEE Componentes -->
<div class="page">
  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:10px 20px;border-radius:8px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:14px;font-weight:700">Relatório de Produção — Ordens &amp; OEE</div>
    <div style="font-size:10px;opacity:.75">${periodoStr}</div>
  </div>

  <div style="display:flex;gap:20px;margin-bottom:20px">
    <div style="flex:1">
      <h2>Ordens de Produção</h2>
      <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap">
        ${funilEfetivo ? [
          ['Total', funilEfetivo.total_ordens||0, '#3b82f6'],
          ['Em Produção', funilEfetivo.iniciadas||0, '#8b5cf6'],
          ['Concluídas', funilEfetivo.concluidas||0, '#22c55e'],
          ['Na Fila', funilEfetivo.nao_iniciadas||0, '#f59e0b'],
        ].map(([l,v,c]) =>
          '<span style="background:' + c + '1a;color:' + c + ';padding:2px 8px;border-radius:10px;font-size:9.5px;font-weight:700">' + l + ': ' + v + '</span>'
        ).join('') : ''}
      </div>
      <table>
        <thead><tr><th>Nº OP</th><th>Peça</th><th>Qtd</th><th>Produzido</th><th>Refugo</th><th>Status</th><th>Progresso</th></tr></thead>
        <tbody>${ordensRows}</tbody>
      </table>
    </div>
    <div style="flex:1">
      <h2>OEE Médio por Componente</h2>
      ${linhas.length > 0 ? (() => {
        const avgDisp = linhas.reduce((s, l) => s + Number(l.disponibilidade || 0), 0) / linhas.length;
        const avgPerf = linhas.reduce((s, l) => s + Number(l.performance || 0), 0) / linhas.length;
        const avgQual = linhas.reduce((s, l) => s + Number(l.qualidade || 0), 0) / linhas.length;
        return (
          '<div style="display:flex;gap:16px;margin-top:8px">' +
          '<div style="text-align:center">' + _pdfSVGGauge(avgDisp, 80) + '<div style="font-size:10px;color:#1d4ed8;font-weight:600">Disponib.</div></div>' +
          '<div style="text-align:center">' + _pdfSVGGauge(avgPerf, 80) + '<div style="font-size:10px;color:#7c3aed;font-weight:600">Performance</div></div>' +
          '<div style="text-align:center">' + _pdfSVGGauge(avgQual, 80) + '<div style="font-size:10px;color:#059669;font-weight:600">Qualidade</div></div>' +
          '</div>'
        );
      })() : '<p style="color:#9ca3af">Sem dados</p>'}
    </div>
  </div>

  <div style="border-top:1px solid #e2e8f0;padding-top:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <h2 style="margin-bottom:0">Paradas por Categoria</h2>
      ${temParadas ? '<span style="font-size:10px;color:#64748b">Total: ' + fmtMin(totalParadaMin) + ' parado</span>' : ''}
    </div>
    ${temParadas
      ? '<table><thead><tr><th>Categoria</th><th>Tempo Total</th><th>%</th><th>Proporção</th></tr></thead><tbody>' + catRows + '</tbody></table>'
      : '<p style="color:#9ca3af;font-size:11px;padding:8px 0">Nenhuma parada registrada neste período.</p>'
    }
  </div>

  <div style="margin-top:auto;padding-top:16px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;font-size:9px;color:#9ca3af;margin-top:24px">
    <span>Sistema PCP — Manufacturing Execution System</span>
    <span>Documento gerado automaticamente em ${new Date().toLocaleString('pt-BR')}</span>
    <span>Página 2 de 3</span>
  </div>
</div>

<!-- PAGE 3: Pareto de paradas detalhado -->
<div class="page">
  <div style="background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;padding:10px 20px;border-radius:8px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-size:14px;font-weight:700">Análise de Paradas e Manutenção</div>
      <div style="font-size:10px;opacity:.85;margin-top:2px">${periodoStr}</div>
    </div>
    <div style="text-align:right;font-size:10px;opacity:.75">Sistema PCP — MES</div>
  </div>

  <div style="display:flex;gap:20px">
    <div style="flex:1">
      <div class="section-badge">Pareto Consolidado</div>
      <table style="margin-top:4px">
        <thead><tr><th>Motivo</th><th>Categoria</th><th>Tempo</th><th>%</th><th>Proporção</th></tr></thead>
        <tbody>${paradaRows}</tbody>
      </table>
    </div>

    <div style="flex:1.6">
      <div class="section-badge">Paradas por Máquina (Top 5 cada)</div>
      <table style="margin-top:4px">
        <thead><tr><th>Máquina</th><th>Motivo</th><th>Categoria</th><th>Tempo</th><th>%</th><th>Barra</th></tr></thead>
        <tbody>${maqParadaRows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-top:auto;padding-top:16px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;font-size:9px;color:#9ca3af;margin-top:24px">
    <span>Sistema PCP — Manufacturing Execution System</span>
    <span>Documento gerado automaticamente em ${new Date().toLocaleString('pt-BR')}</span>
    <span>Página 3 de 3</span>
  </div>
</div>

</body>
</html>`;

  const win = window.open('', '_blank', 'width=1200,height=900');
  if (!win) { alert('Permita popups para gerar o PDF.'); return; }
  win.document.write(html);
  win.document.close();
  win.onload = () => { win.focus(); win.print(); };
}

async function exportarExcel(fabricaData, funil, inicio, fim, turno) {
  const { default: ExcelJS } = await import('exceljs');
  const wb = new ExcelJS.Workbook();
  wb.creator = 'PCP MES';
  wb.created = new Date();

  const fmtDt = (s) => { try { return new Date(s).toLocaleString('pt-BR'); } catch { return s || ''; } };
  const pct = (v) => v == null ? '' : Number(v).toFixed(1) + '%';
  const fmtMin = (m) => {
    const h = Math.floor(m / 60); const mn = Math.round(m % 60);
    return h > 0 ? (h + 'h ' + mn + 'min') : (mn + 'min');
  };
  const turnoNome = turno ? (turno.nome || ('Turno #' + turno.id_ocorrencia)) : '';
  const periodoLabel = turnoNome
    ? (turnoNome + ' | ' + fmtDt(inicio) + ' → ' + fmtDt(fim))
    : (fmtDt(inicio) + ' → ' + fmtDt(fim));

  const hdrFill    = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1E3A5F' } };
  const hdrFont    = { color: { argb: 'FFFFFFFF' }, bold: true };
  const titleFill  = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF2563EB' } };
  const titleFont  = { color: { argb: 'FFFFFFFF' }, bold: true, size: 14 };
  const sub2Fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEFF6FF' } };
  const purpleHdr  = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF7C3AED' } };
  const oeeFont = (v) => ({
    bold: true,
    color: { argb: v >= 85 ? 'FF16A34A' : v >= 60 ? 'FFD97706' : 'FFDC2626' },
  });
  const addBorder = (cell) => {
    cell.border = {
      top:    { style: 'thin', color: { argb: 'FFE2E8F0' } },
      left:   { style: 'thin', color: { argb: 'FFE2E8F0' } },
      bottom: { style: 'thin', color: { argb: 'FFE2E8F0' } },
      right:  { style: 'thin', color: { argb: 'FFE2E8F0' } },
    };
  };

  const linhas = fabricaData?.linhas || [];

  // ── Sheet 1: Resumo Executivo ──────────────────────────────────────────────
  const s1 = wb.addWorksheet('Resumo Executivo', { properties: { tabColor: { argb: 'FF2563EB' } } });
  s1.columns = [{ width: 30 }, { width: 20 }, { width: 20 }, { width: 20 }, { width: 20 }, { width: 20 }];

  s1.mergeCells('A1:F1');
  const t1 = s1.getCell('A1');
  t1.value = 'RELATÓRIO DE PRODUÇÃO — RESUMO EXECUTIVO';
  t1.fill = titleFill; t1.font = titleFont; t1.alignment = { horizontal: 'center', vertical: 'middle' };
  s1.getRow(1).height = 32;

  s1.mergeCells('A2:F2');
  const t2 = s1.getCell('A2');
  t2.value = periodoLabel;
  t2.fill = sub2Fill; t2.font = { bold: true, color: { argb: 'FF1E3A5F' }, size: 11 };
  t2.alignment = { horizontal: 'center', vertical: 'middle' };
  s1.getRow(2).height = 22;
  s1.addRow([]);

  const kpiHdr = s1.addRow(['INDICADORES CHAVE']);
  s1.mergeCells(`A${kpiHdr.number}:F${kpiHdr.number}`);
  kpiHdr.getCell(1).fill = hdrFill; kpiHdr.getCell(1).font = hdrFont;
  kpiHdr.getCell(1).alignment = { horizontal: 'center' };

  // Calcula tempo total parado
  const paradaAggEx = {};
  linhas.forEach(l => {
    (l.pareto_paradas || []).forEach(p => { paradaAggEx[p.motivo] = (paradaAggEx[p.motivo] || 0) + p.minutos; });
  });
  const totalParadaMinEx = Object.values(paradaAggEx).reduce((s, v) => s + v, 0);

  const kpiData = [
    ['OEE Global', (fabricaData?.oee_global != null ? Number(fabricaData.oee_global).toFixed(1) + '%' : '—')],
    ['Linhas Ativas', linhas.length],
    ['Total de Ordens', funilXls?.total_ordens ?? allOrdensXls.length],
    ['Ordens Concluídas', funilXls?.concluidas ?? allOrdensXls.filter(o => o.status === 'finalizado').length],
    ['Ordens em Produção', funilXls?.iniciadas ?? allOrdensXls.filter(o => o.status === 'em_producao').length],
    ['Ordens Na Fila', funilXls?.nao_iniciadas ?? allOrdensXls.filter(o => o.status === 'fila').length],
    ['Ordens Atrasadas', funilXls?.atrasadas || 0],
    ['Tempo Total Parado', totalParadaMinEx > 0 ? fmtMin(totalParadaMinEx) : '—'],
    ['Tipos de Parada Registrados', Object.keys(paradaAggEx).length],
  ];
  kpiData.forEach(([label, val]) => {
    const row = s1.addRow([label, val]);
    row.getCell(1).font = { bold: true };
    row.getCell(2).alignment = { horizontal: 'right' };
    addBorder(row.getCell(1)); addBorder(row.getCell(2));
  });

  // ── Sheet 2: Por Linha ────────────────────────────────────────────────────
  const s2 = wb.addWorksheet('Por Linha', { properties: { tabColor: { argb: 'FF22C55E' } } });
  s2.columns = [{ width: 24 }, { width: 14 }, { width: 16 }, { width: 16 }, { width: 14 }, { width: 16 }, { width: 16 }, { width: 16 }];

  s2.mergeCells('A1:H1');
  const s2t = s2.getCell('A1');
  s2t.value = 'PERFORMANCE POR LINHA' + (turnoNome ? ' — ' + turnoNome : '');
  s2t.fill = titleFill; s2t.font = titleFont; s2t.alignment = { horizontal: 'center', vertical: 'middle' };
  s2.getRow(1).height = 28;
  s2.mergeCells('A2:H2');
  const s2p = s2.getCell('A2');
  s2p.value = periodoLabel;
  s2p.fill = sub2Fill; s2p.font = { bold: true, color: { argb: 'FF1E3A5F' } };
  s2p.alignment = { horizontal: 'center', vertical: 'middle' };
  s2.addRow([]);

  const s2hdr = s2.addRow(['Linha', 'OEE (%)', 'Disponib. (%)', 'Performance (%)', 'Qualidade (%)', 'Produzido', 'Meta', 'Atingimento (%)']);
  s2hdr.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });
  s2.getRow(s2hdr.number).height = 20;

  linhas.forEach((l, i) => {
    const oee = Number(l.oee || 0);
    const ating = l.meta_total ? (Number(l.realizado || 0) / Number(l.meta_total) * 100) : null;
    const row = s2.addRow([
      l.nome || ('Linha ' + l.id_linha),
      pct(l.oee), pct(l.disponibilidade), pct(l.performance), pct(l.qualidade),
      l.realizado || 0, l.meta_total || 0,
      ating != null ? ating.toFixed(1) + '%' : '—',
    ]);
    row.getCell(1).font = { bold: true };
    row.getCell(2).font = oeeFont(oee);
    const bg = i % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF';
    row.eachCell(c => {
      c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      c.alignment = { horizontal: c === row.getCell(1) ? 'left' : 'center' };
      addBorder(c);
    });
    if (oee >= 85) row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF0FDF4' } };
    else if (oee < 60) row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFEF2F2' } };
    else row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF7ED' } };
  });

  // ── Sheet 3: Por Máquina ──────────────────────────────────────────────────
  const s3 = wb.addWorksheet('Por Máquina', { properties: { tabColor: { argb: 'FF8B5CF6' } } });
  s3.columns = [{ width: 26 }, { width: 20 }, { width: 14 }, { width: 16 }, { width: 16 }, { width: 14 }, { width: 18 }];

  s3.mergeCells('A1:G1');
  const s3t = s3.getCell('A1');
  s3t.value = 'PERFORMANCE POR MÁQUINA' + (turnoNome ? ' — ' + turnoNome : '');
  s3t.fill = titleFill; s3t.font = titleFont; s3t.alignment = { horizontal: 'center', vertical: 'middle' };
  s3.getRow(1).height = 28;
  s3.addRow([]);

  const s3hdr = s3.addRow(['Máquina', 'Linha', 'OEE (%)', 'Disponib. (%)', 'Performance (%)', 'Produzido', 'Status']);
  s3hdr.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });

  const allMaquinas = linhas.flatMap(l => (l.maquinas || []).map(m => ({ ...m, linhaNome: l.nome || ('Linha ' + l.id_linha) })));
  allMaquinas.forEach((m, i) => {
    const oee = Number(m.oee || 0);
    const row = s3.addRow([
      m.nome || ('Máquina ' + m.id),
      m.linhaNome,
      pct(m.oee), pct(m.disponibilidade), pct(m.performance),
      m.realizado || m.produzido || 0,
      m.status || '—',
    ]);
    const bg = i % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF';
    row.eachCell(c => {
      c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      c.alignment = { horizontal: 'center' };
      addBorder(c);
    });
    row.getCell(1).font = { bold: true }; row.getCell(1).alignment = { horizontal: 'left' };
    row.getCell(2).alignment = { horizontal: 'left' };
    row.getCell(3).font = oeeFont(oee);
  });
  if (allMaquinas.length === 0) {
    const r = s3.addRow(['Sem dados de máquinas disponíveis']);
    s3.mergeCells(`A${r.number}:G${r.number}`);
    r.getCell(1).alignment = { horizontal: 'center' };
    r.getCell(1).font = { italic: true, color: { argb: 'FF9CA3AF' } };
  }

  // ── Sheet 4: Ordens de Produção (lista real) ─────────────────────────────
  const allOrdensXls = linhas.flatMap(l => (l.ordens || []).map(o => ({
    ...o, linhaNome: l.nome || ('Linha ' + l.id_linha),
  })));
  // Funil derivado das ordens reais se não disponível diretamente
  const funilXls = funil || (allOrdensXls.length > 0 ? {
    total_ordens:  allOrdensXls.length,
    concluidas:    allOrdensXls.filter(o => o.status === 'finalizado'   || o.conclusao >= 100).length,
    iniciadas:     allOrdensXls.filter(o => o.status === 'em_producao').length,
    nao_iniciadas: allOrdensXls.filter(o => o.status === 'fila').length,
    atrasadas:     0,
  } : null);

  const s4 = wb.addWorksheet('Ordens de Produção', { properties: { tabColor: { argb: 'FFF59E0B' } } });
  s4.columns = [
    { width: 16 }, { width: 28 }, { width: 14 }, { width: 14 }, { width: 12 }, { width: 10 }, { width: 18 }, { width: 20 },
  ];

  s4.mergeCells('A1:H1');
  const s4t = s4.getCell('A1');
  s4t.value = 'ORDENS DE PRODUÇÃO' + (turnoNome ? ' — ' + turnoNome : '');
  s4t.fill = titleFill; s4t.font = titleFont; s4t.alignment = { horizontal: 'center', vertical: 'middle' };
  s4.getRow(1).height = 28;

  // Linha de resumo do funil
  if (funilXls) {
    s4.mergeCells('A2:H2');
    const s4summ = s4.getCell('A2');
    s4summ.value = `Total: ${funilXls.total_ordens}  |  Em Produção: ${funilXls.iniciadas}  |  Concluídas: ${funilXls.concluidas}  |  Na Fila: ${funilXls.nao_iniciadas}`;
    s4summ.fill = sub2Fill; s4summ.font = { bold: true, color: { argb: 'FF1E3A5F' } };
    s4summ.alignment = { horizontal: 'center', vertical: 'middle' };
  }

  s4.addRow([]);
  const s4hdr = s4.addRow(['Nº OP', 'Peça / Produto', 'Quantidade', 'Produzido', 'Refugo', '% Conclusão', 'Status', 'Linha']);
  s4hdr.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });
  s4.getRow(s4hdr.number).height = 20;

  const statusArgb = (s) => s === 'finalizado' ? 'FF16A34A' : s === 'em_producao' ? 'FF2563EB' : s === 'cancelada' ? 'FFDC2626' : 'FF92400E';
  const statusLbl  = (s) => s === 'finalizado' ? 'Concluída' : s === 'em_producao' ? 'Em Produção' : s === 'fila' ? 'Na Fila' : s === 'cancelada' ? 'Cancelada' : s || '—';
  const statusBg   = (s) => s === 'finalizado' ? 'FFF0FDF4' : s === 'em_producao' ? 'FFEFF6FF' : s === 'cancelada' ? 'FFFEF2F2' : 'FFFFF7ED';

  if (allOrdensXls.length > 0) {
    allOrdensXls.forEach((o, i) => {
      const conc = o.conclusao ?? (o.quantidade > 0 ? Math.round(o.produzido / o.quantidade * 100) : 0);
      const row = s4.addRow([
        o.numero || '—',
        o.peca   || '—',
        o.quantidade || 0,
        o.produzido  || 0,
        o.refugo     || 0,
        conc + '%',
        statusLbl(o.status),
        o.linhaNome || '—',
      ]);
      const bg = i % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF';
      row.eachCell(c => {
        c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
        c.alignment = { horizontal: 'center' };
        addBorder(c);
      });
      row.getCell(1).font = { bold: true }; row.getCell(1).alignment = { horizontal: 'left' };
      row.getCell(2).alignment = { horizontal: 'left' };
      row.getCell(7).font = { bold: true, color: { argb: statusArgb(o.status) } };
      row.getCell(7).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: statusBg(o.status) } };
      // Highlight conclusao
      if (conc >= 100) row.getCell(6).font = { bold: true, color: { argb: 'FF16A34A' } };
      else if (conc >= 50) row.getCell(6).font = { color: { argb: 'FFD97706' } };
      else row.getCell(6).font = { color: { argb: 'FFDC2626' } };
    });
  } else {
    const r = s4.addRow(['Nenhuma ordem de produção encontrada para este período']);
    s4.mergeCells(`A${r.number}:H${r.number}`);
    r.getCell(1).font = { italic: true, color: { argb: 'FF9CA3AF' } };
    r.getCell(1).alignment = { horizontal: 'center' };
  }

  // ── Sheet 5: Motivos de Parada ────────────────────────────────────────────
  const s5 = wb.addWorksheet('Motivos de Parada', { properties: { tabColor: { argb: 'FF7C3AED' } } });
  s5.columns = [
    { width: 30 }, { width: 20 }, { width: 18 }, { width: 16 }, { width: 16 }, { width: 24 },
  ];

  s5.mergeCells('A1:F1');
  const s5t = s5.getCell('A1');
  s5t.value = 'ANÁLISE DE PARADAS E MANUTENÇÃO' + (turnoNome ? ' — ' + turnoNome : '');
  s5t.fill = purpleHdr; s5t.font = titleFont; s5t.alignment = { horizontal: 'center', vertical: 'middle' };
  s5.getRow(1).height = 28;
  s5.mergeCells('A2:F2');
  const s5p = s5.getCell('A2');
  s5p.value = periodoLabel;
  s5p.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFAF5FF' } };
  s5p.font = { bold: true, color: { argb: 'FF7C3AED' } };
  s5p.alignment = { horizontal: 'center', vertical: 'middle' };
  s5.addRow([]);

  // ─ Resumo por categoria ─
  const s5CatHdr = s5.addRow(['RESUMO POR CATEGORIA']);
  s5.mergeCells(`A${s5CatHdr.number}:F${s5CatHdr.number}`);
  s5CatHdr.getCell(1).fill = purpleHdr; s5CatHdr.getCell(1).font = hdrFont;
  s5CatHdr.getCell(1).alignment = { horizontal: 'center' };

  const catHdrRow = s5.addRow(['Categoria', 'Tempo Total', '% do Total', 'Qtd Motivos', '', '']);
  catHdrRow.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });

  // Build category aggregation
  const catAggEx = {};
  linhas.forEach(l => {
    (l.pareto_paradas || []).forEach(p => {
      const c = _categorizarMotivo(p.motivo);
      if (!catAggEx[c.cat]) catAggEx[c.cat] = { argb: c.argb, bgArgb: c.bgArgb, mins: 0, count: 0 };
      catAggEx[c.cat].mins  += p.minutos;
      catAggEx[c.cat].count += 1;
    });
  });
  const catSortedEx = Object.entries(catAggEx).sort((a, b) => b[1].mins - a[1].mins);
  const totMin = catSortedEx.reduce((s, [, v]) => s + v.mins, 0);

  catSortedEx.forEach(([cat, v], i) => {
    const row = s5.addRow([cat, fmtMin(v.mins), totMin > 0 ? (v.mins / totMin * 100).toFixed(1) + '%' : '—', v.count]);
    row.getCell(1).font = { bold: true, color: { argb: v.argb } };
    row.getCell(2).font = { bold: true, color: { argb: v.argb } };
    row.getCell(3).alignment = { horizontal: 'center' };
    row.getCell(4).alignment = { horizontal: 'center' };
    const bg = i % 2 === 0 ? v.bgArgb : 'FFFFFFFF';
    row.eachCell(c => {
      c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg || 'FFFFFFFF' } };
      addBorder(c);
    });
  });
  if (catSortedEx.length === 0) {
    const r = s5.addRow(['Nenhuma parada registrada neste período']);
    s5.mergeCells(`A${r.number}:F${r.number}`);
    r.getCell(1).font = { italic: true, color: { argb: 'FF9CA3AF' } };
    r.getCell(1).alignment = { horizontal: 'center' };
  }

  s5.addRow([]);

  // ─ Pareto consolidado (top 20) ─
  const s5ParetoHdr = s5.addRow(['PARETO CONSOLIDADO — TOP 20 MOTIVOS']);
  s5.mergeCells(`A${s5ParetoHdr.number}:F${s5ParetoHdr.number}`);
  s5ParetoHdr.getCell(1).fill = purpleHdr; s5ParetoHdr.getCell(1).font = hdrFont;
  s5ParetoHdr.getCell(1).alignment = { horizontal: 'center' };

  const paretoColHdr = s5.addRow(['Motivo', 'Categoria', 'Tempo Total', '% do Total', 'Acumulado %', '']);
  paretoColHdr.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });

  // Aggregate pareto across all lines
  const paradaAggEx2 = {};
  linhas.forEach(l => {
    (l.pareto_paradas || []).forEach(p => { paradaAggEx2[p.motivo] = (paradaAggEx2[p.motivo] || 0) + p.minutos; });
  });
  const totParetMin = Object.values(paradaAggEx2).reduce((s, v) => s + v, 0);
  const paretoSorted = Object.entries(paradaAggEx2).sort((a, b) => b[1] - a[1]).slice(0, 20);
  let acumPct = 0;
  paretoSorted.forEach(([mot, mins], i) => {
    const c = _categorizarMotivo(mot);
    const pctVal = totParetMin > 0 ? (mins / totParetMin * 100) : 0;
    acumPct += pctVal;
    const row = s5.addRow([mot, c.cat, fmtMin(mins), pctVal.toFixed(1) + '%', acumPct.toFixed(1) + '%']);
    row.getCell(1).font = { bold: true };
    row.getCell(2).font = { color: { argb: c.argb } };
    row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: c.bgArgb || 'FFFFFFFF' } };
    row.getCell(3).font = { bold: true, color: { argb: c.argb } };
    [3, 4, 5].forEach(n => row.getCell(n).alignment = { horizontal: 'center' });
    const bg = i % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF';
    row.eachCell(c2 => {
      if (!c2.fill || c2.fill.fgColor?.argb === bg) c2.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      addBorder(c2);
    });
  });
  if (paretoSorted.length === 0) {
    const r = s5.addRow(['Nenhum motivo de parada registrado']);
    s5.mergeCells(`A${r.number}:F${r.number}`);
    r.getCell(1).font = { italic: true, color: { argb: 'FF9CA3AF' } };
    r.getCell(1).alignment = { horizontal: 'center' };
  }

  s5.addRow([]);

  // ─ Detalhe por máquina ─
  const s5MaqHdr = s5.addRow(['PARADAS POR MÁQUINA']);
  s5.mergeCells(`A${s5MaqHdr.number}:F${s5MaqHdr.number}`);
  s5MaqHdr.getCell(1).fill = purpleHdr; s5MaqHdr.getCell(1).font = hdrFont;
  s5MaqHdr.getCell(1).alignment = { horizontal: 'center' };

  const maqDetailHdr = s5.addRow(['Máquina', 'Motivo', 'Categoria', 'Tempo', '% na Máquina', 'Acumulado %']);
  maqDetailHdr.eachCell(c => { c.fill = hdrFill; c.font = hdrFont; c.alignment = { horizontal: 'center' }; addBorder(c); });

  allMaquinas.forEach((m) => {
    const paradas = m.pareto_paradas || [];
    if (paradas.length === 0) return;
    paradas.forEach((p, pi) => {
      const c = _categorizarMotivo(p.motivo);
      const row = s5.addRow([
        pi === 0 ? (m.nome || ('Máquina ' + m.id)) : '',
        p.motivo,
        c.cat,
        fmtMin(p.minutos),
        p.percentual.toFixed(1) + '%',
        p.acumulado.toFixed(1) + '%',
      ]);
      row.getCell(1).font = { bold: pi === 0 };
      row.getCell(3).font = { color: { argb: c.argb } };
      row.getCell(3).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: c.bgArgb || 'FFFFFFFF' } };
      row.getCell(4).font = { bold: true, color: { argb: c.argb } };
      [4, 5, 6].forEach(n => row.getCell(n).alignment = { horizontal: 'center' });
      row.eachCell(c2 => {
        if (!c2.fill || !c2.fill.fgColor?.argb?.startsWith('FF') || c2.fill.fgColor.argb === 'FF000000')
          c2.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: pi % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF' } };
        addBorder(c2);
      });
    });
  });

  // ── Download ──────────────────────────────────────────────────────────────
  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const label = turnoNome ? turnoNome.replace(/[^a-zA-Z0-9]/g, '_') : 'periodo';
  a.href = url; a.download = 'relatorio_pcp_' + label + '.xlsx';
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}


// ─── Quick Excel button (async wrapper) ──────────────────────────────────────

function QuickExcelBtn({ fabricaData, funil, inicio, fim }) {
  const [exp, setExp] = useState(false);
  async function go() {
    setExp(true);
    try { await exportarExcel(fabricaData, funil, inicio, fim); }
    finally { setExp(false); }
  }
  return (
    <button className="hi-buscar-btn hi-export-btn hi-export-btn--excel"
      onClick={go} disabled={exp} title="Exportar planilha Excel (4 abas formatadas)">
      {exp ? <><Spinner size={14} /> Excel...</> : "📊 Excel"}
    </button>
  );
}

// ─── Aba Relatório ───────────────────────────────────────────────────────────

function RelatorioTab({ fabricaData, funil, inicio, fim, onBuscar, loading }) {
  const [exporting, setExporting] = useState(false);

  async function handleExcel() {
    if (!fabricaData) return;
    setExporting(true);
    try { await exportarExcel(fabricaData, funil, inicio, fim); }
    finally { setExporting(false); }
  }

  const totalProd = fabricaData?.linhas.reduce((s, l) => s + (l.realizado   || 0), 0) ?? 0;
  const totalMeta = fabricaData?.linhas.reduce((s, l) => s + (l.meta_total  || 0), 0) ?? 0;
  const allMaq    = fabricaData?.linhas.flatMap((l) => l.maquinas || []) ?? [];
  const totalRej  = allMaq.reduce((s, m) => s + (m.reprovado || 0), 0);
  const taxaRej   = (totalProd + totalRej) > 0 ? +((totalRej / (totalProd + totalRej)) * 100).toFixed(1) : 0;
  const ader      = totalMeta > 0 ? +((totalProd / totalMeta) * 100).toFixed(1) : null;
  const totalOPs  = funil ? Object.values(funil).reduce((s, v) => s + (v?.qty || 0), 0) : 0;

  if (!fabricaData) {
    return (
      <div className="hi-tab-content">
        <div className="hi-relatorio-empty">
          <div className="hi-relatorio-empty-icon">📋</div>
          <div className="hi-relatorio-empty-title">Nenhum dado carregado</div>
          <div className="hi-relatorio-empty-sub">
            Volte ao painel e clique em "Buscar Dados" para carregar o período desejado antes de gerar relatórios.
          </div>
          <button className="hi-buscar-btn" onClick={onBuscar} disabled={loading} style={{ marginTop: 12 }}>
            {loading ? <><Spinner size={14} /> Buscando...</> : "Buscar Dados Agora"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="hi-tab-content">

      {/* ── Export actions ── */}
      <div className="hi-relatorio-header">
        <div className="hi-relatorio-header-left">
          <span className="hi-relatorio-badge">Pronto para exportar</span>
          <h2 className="hi-relatorio-title">Gerar Relatório</h2>
          <p className="hi-relatorio-sub">
            {fabricaData.linhas.length} linhas · {allMaq.length} máquinas · período selecionado
          </p>
        </div>
        <div className="hi-relatorio-export-btns">
          <button className="hi-export-card hi-export-card--pdf"
            onClick={() => exportarPDF(fabricaData, funil, inicio, fim)}>
            <div className="hi-export-card-icon">📄</div>
            <div className="hi-export-card-body">
              <div className="hi-export-card-title">Relatório PDF</div>
              <div className="hi-export-card-sub">2 páginas · A4 Paisagem · OEE gauges · Tabelas profissionais</div>
            </div>
          </button>
          <button className="hi-export-card hi-export-card--excel"
            onClick={handleExcel} disabled={exporting}>
            <div className="hi-export-card-icon">{exporting ? "⏳" : "📊"}</div>
            <div className="hi-export-card-body">
              <div className="hi-export-card-title">{exporting ? "Gerando planilha..." : "Planilha Excel"}</div>
              <div className="hi-export-card-sub">{funil ? "4" : "3"} abas · Células formatadas · Download direto</div>
            </div>
          </button>
        </div>
      </div>

      {/* ── What's included ── */}
      <div className="hi-section">
        <div className="hi-section-header">
          <span className="hi-section-title">Conteúdo dos Relatórios</span>
          <span className="hi-section-sub">O que será incluído na exportação</span>
        </div>
        <div className="hi-relatorio-docs">
          <div className="hi-relatorio-doc hi-relatorio-doc--pdf">
            <div className="hi-relatorio-doc-hdr">
              <span className="hi-relatorio-doc-icon">📄</span>
              <span className="hi-relatorio-doc-title">PDF — 2 Páginas A4 Paisagem</span>
            </div>
            <ul className="hi-relatorio-doc-list">
              <li><strong>Página 1:</strong> KPIs executivos (6 cards) · Gauges OEE, Disponib., Perf., Qualidade · Tabela de linhas com barras de progresso · {funil ? "Funil de ordens · " : ""}Resumo do período</li>
              <li><strong>Página 2:</strong> Detalhamento por máquina com OEE breakdown completo, aderência à meta, status e rejeições</li>
            </ul>
          </div>
          <div className="hi-relatorio-doc hi-relatorio-doc--excel">
            <div className="hi-relatorio-doc-hdr">
              <span className="hi-relatorio-doc-icon">📊</span>
              <span className="hi-relatorio-doc-title">Excel — {funil ? "4" : "3"} Abas Formatadas</span>
            </div>
            <ul className="hi-relatorio-doc-list">
              <li><strong>Resumo Executivo:</strong> KPIs globais + performance por linha + {funil ? "funil de ordens" : "dados do período"}</li>
              <li><strong>Por Linha:</strong> OEE · Disponibilidade · Performance · Qualidade · Aderência · Rejeições</li>
              <li><strong>Por Máquina:</strong> Breakdown completo OEE de cada máquina com FPY</li>
              {funil && <li><strong>Ordens de Produção:</strong> Funil com quantidades, peças e percentuais por status</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* ── Data summary ── */}
      <div className="hi-section">
        <div className="hi-section-header">
          <span className="hi-section-title">Resumo dos Dados</span>
          <span className="hi-section-sub">Dados que serão exportados</span>
        </div>
        <div className="hi-kpi-row">
          <KPICard icon="⚡" label="OEE Global"
            value={fabricaData.oee_global != null ? `${fabricaData.oee_global}` : "—"}
            unit={fabricaData.oee_global != null ? "%" : ""}
            color={oeeColor(fabricaData.oee_global)} sub={oeeLabel(fabricaData.oee_global)} />
          <KPICard icon="📦" label="Produção Total"
            value={totalProd.toLocaleString("pt-BR")} unit="un" color="#3b82f6"
            sub={`Meta: ${totalMeta.toLocaleString("pt-BR")} un`} />
          <KPICard icon="📊" label="Aderência à Meta"
            value={ader ?? "—"} unit={ader != null ? "%" : ""}
            color={oeeColor(ader)} sub={`${totalProd} / ${totalMeta} un`} />
          <KPICard icon="🔍" label="Taxa de Rejeição"
            value={taxaRej} unit="%"
            color={taxaRej > 10 ? "#dc2626" : "#16a34a"}
            sub={`${totalRej} peças rejeitadas`} />
          <KPICard icon="🏭" label="Linhas"
            value={fabricaData.linhas.length} color="#8b5cf6"
            sub={`${allMaq.length} máquinas monitoradas`} />
          {funil && (
            <KPICard icon="📋" label="OPs no Período"
              value={totalOPs} color="#f59e0b"
              sub={`${funil.finalizado?.qty || 0} finalizadas · ${funil.em_producao?.qty || 0} em produção`} />
          )}
        </div>
      </div>

      {/* ── Lines table preview ── */}
      <div className="hi-section">
        <div className="hi-section-header">
          <span className="hi-section-title">Linhas de Produção</span>
          <span className="hi-section-sub">Prévia dos dados exportados</span>
        </div>
        <div className="hi-table-wrap">
          <table className="hi-table">
            <thead>
              <tr>
                <th>Linha</th><th>OEE</th><th>Produzido</th>
                <th>Meta</th><th>Aderência</th><th>Máquinas</th><th>Rejeitado</th>
              </tr>
            </thead>
            <tbody>
              {fabricaData.linhas.map((l) => {
                const a   = l.meta_total > 0 ? +((l.realizado / l.meta_total) * 100).toFixed(1) : null;
                const rej = (l.maquinas || []).reduce((s, m) => s + (m.reprovado || 0), 0);
                return (
                  <tr key={l.id}>
                    <td className="hi-td-name">{l.nome}</td>
                    <td style={{ color: oeeColor(l.oee), fontWeight: 800 }}>{fmtPct(l.oee)}</td>
                    <td>{(l.realizado || 0).toLocaleString("pt-BR")}</td>
                    <td style={{ color: "#9ca3af" }}>{(l.meta_total || 0).toLocaleString("pt-BR")}</td>
                    <td style={{ color: oeeColor(a), fontWeight: 700 }}>{a != null ? `${a}%` : "—"}</td>
                    <td>{l.maquinas?.length || 0}</td>
                    <td style={{ color: rej > 0 ? "#dc2626" : "#16a34a", fontWeight: rej > 0 ? 700 : 400 }}>{rej}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}

// ─── Tabs ────────────────────────────────────────────────────────────────────

const TABS = [
  { key: "turno",     label: "🔄 Detalhes do Turno", sub: "Principal"  },
  { key: "fabrica",   label: "🏭 Visão Geral",        sub: "Fábrica"    },
  { key: "linha",     label: "🔧 Por Linha",          sub: "Análise"    },
  { key: "maquina",   label: "⚙️ Por Máquina",       sub: "Drill-down" },
  { key: "relatorio", label: "📋 Relatórios",         sub: "Exportar"   },
];

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Historico() {
  // ── Seleção de turno (filtro primário) ──
  const [allLinhas,     setAllLinhas]     = useState([]);
  const [selLinhaId,    setSelLinhaId]    = useState("");
  const [turnoOpts,     setTurnoOpts]     = useState([]);
  const [selectedTurno, setSelectedTurno] = useState(null);
  const [activeTab,     setActiveTab]     = useState("turno");

  // ── Dados carregados ──
  const [fabricaData, setFabricaData] = useState(null);
  const [funil,       setFunil]       = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);

  // ── Derivados do turno selecionado ──
  const inicio = selectedTurno ? (selectedTurno.dt_real_inicio || selectedTurno.dt_inicio || "") : "";
  const fim    = selectedTurno ? (selectedTurno.dt_real_fim   || selectedTurno.dt_fim    || new Date().toISOString()) : "";

  // Carrega linhas ao montar
  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then((r) => r.json())
      .then((data) => {
        const list = data || [];
        setAllLinhas(list);
        if (list.length > 0) setSelLinhaId(String(list[0].id));
      })
      .catch(() => {});
  }, []);

  // Carrega turnos quando a linha muda
  useEffect(() => {
    if (!selLinhaId) { setTurnoOpts([]); setSelectedTurno(null); return; }
    fetch(`${API_BASE}/api/config/lines/${selLinhaId}/turnos/historico?limit=40`)
      .then((r) => r.json())
      .then((list) => {
        const opts = (list || []).filter((t) => t.status !== "agendado");
        setTurnoOpts(opts);
        // Auto-seleciona o turno mais recente
        if (opts.length > 0) {
          const keep = opts.find((t) => t.id_ocorrencia === selectedTurno?.id_ocorrencia);
          setSelectedTurno(keep || opts[0]);
        } else {
          setSelectedTurno(null);
        }
      })
      .catch(() => { setTurnoOpts([]); setSelectedTurno(null); });
  }, [selLinhaId]);

  function fmtTurnoLbl(t) {
    const dt = t.dt_real_inicio || t.dt_inicio;
    if (!dt) return t.nome;
    const d = new Date(dt);
    return `${t.nome} — ${d.toLocaleDateString("pt-BR")} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function buscar() {
    if (!selectedTurno) return;
    const di = selectedTurno.dt_real_inicio || selectedTurno.dt_inicio;
    const df = selectedTurno.dt_real_fim   || selectedTurno.dt_fim || new Date().toISOString();
    setLoading(true); setError(null); setFabricaData(null); setFunil(null);
    Promise.all([
      fetch(`${API_BASE}/api/historico?data_inicio=${encode(di)}&data_fim=${encode(df)}`)
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      fetch(`${API_BASE}/api/historico/ordens?data_inicio=${encode(di)}&data_fim=${encode(df)}`)
        .then((r) => r.ok ? r.json() : null),
    ])
      .then(([fab, fun]) => { setFabricaData(fab); setFunil(fun); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }

  const aderenciaTurno = selectedTurno && selectedTurno.meta > 0
    ? Math.round((selectedTurno.produzido / selectedTurno.meta) * 100) : null;

  return (
    <div className="hi-root">

      {/* ── Header — seleção de turno ─────────────────────────────────────── */}
      <div className="hi-filter-card">
        <div className="hi-filter-top">
          <div className="hi-filter-title-block">
            <h1 className="hi-page-title">Analytics de Produção</h1>
            <p className="hi-page-sub">Turno como filtro principal — todos os indicadores refletem o turno selecionado</p>
          </div>
          {fabricaData && (
            <div className="hi-quick-export">
              <button className="hi-buscar-btn hi-export-btn hi-export-btn--pdf"
                onClick={() => exportarPDF(fabricaData, funil, inicio, fim, selectedTurno)}
                title="Gerar PDF profissional">📄 PDF</button>
              <QuickExcelBtn fabricaData={fabricaData} funil={funil} inicio={inicio} fim={fim} turno={selectedTurno} />
            </div>
          )}
        </div>

        <div className="hi-filter-row">
          <div className="hi-filter-field">
            <label className="hi-filter-label">Linha de Referência</label>
            <select className="hi-filter-input"
              value={selLinhaId}
              onChange={(e) => { setSelLinhaId(e.target.value); setFabricaData(null); setFunil(null); }}>
              <option value="">— Selecione a linha —</option>
              {allLinhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
            </select>
          </div>
          <div className="hi-filter-sep">→</div>
          <div className="hi-filter-field hi-filter-field--wide">
            <label className="hi-filter-label">Turno</label>
            <select className="hi-filter-input"
              value={selectedTurno?.id_ocorrencia || ""}
              onChange={(e) => {
                const t = turnoOpts.find((t) => String(t.id_ocorrencia) === e.target.value) || null;
                setSelectedTurno(t);
                setFabricaData(null); setFunil(null);
              }}
              disabled={!selLinhaId || turnoOpts.length === 0}>
              <option value="">— Selecione o turno —</option>
              {turnoOpts.map((t) => (
                <option key={t.id_ocorrencia} value={t.id_ocorrencia}>{fmtTurnoLbl(t)}</option>
              ))}
            </select>
          </div>
          <button className="hi-buscar-btn" onClick={buscar} disabled={loading || !selectedTurno}>
            {loading ? <><Spinner size={14} /> Carregando...</> : "Ver Dados da Fábrica"}
          </button>
        </div>

        {/* Banner do turno selecionado */}
        {selectedTurno && (
          <div className="hi-turno-banner">
            <div className="hi-turno-banner-left">
              <span className="hi-turno-banner-nome">{selectedTurno.nome}</span>
              <span className={`hi-turno-banner-status hi-turno-banner-status--${selectedTurno.status}`}>
                {selectedTurno.status === "finalizado" ? "Finalizado"
                  : selectedTurno.status === "em_andamento" ? "Em andamento"
                  : selectedTurno.status}
              </span>
            </div>
            <div className="hi-turno-banner-times">
              <span>Início: <strong>{selectedTurno.dt_real_inicio ? new Date(selectedTurno.dt_real_inicio).toLocaleString("pt-BR") : "—"}</strong></span>
              <span>Fim: <strong>{selectedTurno.dt_real_fim ? new Date(selectedTurno.dt_real_fim).toLocaleString("pt-BR") : "Em curso"}</strong></span>
            </div>
            <div className="hi-turno-banner-kpis">
              <span>Meta: <strong>{selectedTurno.meta ?? "—"}</strong></span>
              <span>Produzido: <strong style={{ color: oeeColor(aderenciaTurno) }}>{selectedTurno.produzido ?? "—"}</strong></span>
              {aderenciaTurno !== null && (
                <span style={{ color: oeeColor(aderenciaTurno), fontWeight: 700 }}>
                  Aderência: {aderenciaTurno}%
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {error && <div className="hi-error">⚠ {error}</div>}

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="hi-tabs">
        {TABS.map((t) => (
          <button key={t.key}
            className={`hi-tab${activeTab === t.key ? " hi-tab--active" : ""}`}
            onClick={() => setActiveTab(t.key)}>
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
          {activeTab === "turno"     && (
            <TurnoTab selectedTurno={selectedTurno} selectedLinhaId={selLinhaId} />
          )}
          {activeTab === "fabrica"   && <FabricaTab data={fabricaData} funil={funil} />}
          {activeTab === "linha"     && (
            <LinhaTab linhas={fabricaData?.linhas} inicio={inicio} fim={fim} defaultLinhaId={selLinhaId} />
          )}
          {activeTab === "maquina"   && (
            <MaquinaTab linhas={fabricaData?.linhas} inicio={inicio} fim={fim} />
          )}
          {activeTab === "relatorio" && (
            <RelatorioTab fabricaData={fabricaData} funil={funil} inicio={inicio} fim={fim}
              turno={selectedTurno} onBuscar={buscar} loading={loading} />
          )}
        </>
      )}

    </div>
  );
}
