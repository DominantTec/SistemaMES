import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import "./LinhaDetalhe.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE  = API_BASE.replace(/^http/, "ws");

// ── helpers de status ────────────────────────────────────────────────────────
const STATUS_MAP = {
  produzindo:   { label: "PRODUZINDO",  color: "#16a34a", bg: "#dcfce7", dot: "#16a34a" },
  alerta:       { label: "ALERTA",      color: "#d97706", bg: "#fef3c7", dot: "#d97706" },
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
  if (isNaN(n) || val === null) return "#d1d5db";
  if (n >= 75) return "#16a34a";
  if (n >= 50) return "#d97706";
  return "#dc2626";
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "-";
  return `${v}${suffix}`;
}

// ── sub-componentes ──────────────────────────────────────────────────────────

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

function MachineCard({ machine, metrica }) {
  const st = getStatus(machine.status);
  const isProduzindo = machine.status?.toLowerCase().includes("produz");
  const isParada = !isProduzindo;

  const oeeVal = machine.oee;
  const oc = oeeColor(isProduzindo ? oeeVal : null);

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
          <div className="ld-mc-oee-val" style={{ color: isParada ? "#d1d5db" : oc }}>
            {isParada ? "0%" : `${oeeVal}%`}
          </div>
          <div className="ld-mc-oee-label">OEE ATUAL</div>
        </div>

        {machine.op && (
          <div className="ld-mc-op-block">
            <div className="ld-mc-op">{machine.op}</div>
            <div className="ld-mc-peca">Peça: {machine.peca}</div>
          </div>
        )}

        {isParada && machine.motivo_parada && (
          <div
            className="ld-mc-motivo"
            style={{ color: st.color, background: st.bg }}
          >
            {machine.motivo_parada}
          </div>
        )}
      </div>

      {/* barras de métricas */}
      {isProduzindo ? (
        <div className="ld-mc-metrics">
          {metrica === "OEE" && (
            <>
              <MetricRow label="Disponibilidade" value={machine.disponibilidade} />
              <MetricRow label="Performance"     value={machine.performance} />
            </>
          )}
          {metrica === "Disponibilidade" && (
            <>
              <MetricRow label="Disponibilidade" value={machine.disponibilidade} />
              <MetricRow label="Qualidade"       value={machine.qualidade} />
            </>
          )}
          {metrica === "Desempenho" && (
            <>
              <MetricRow label="Performance" value={machine.performance} />
              <MetricRow label="Qualidade"   value={machine.qualidade} />
            </>
          )}
        </div>
      ) : (
        /* máquina parada — mostra info de parada */
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
          {machine.status_parada && (
            <div className="ld-mc-parada-item">
              <span className="ld-mc-parada-label">STATUS</span>
              <span className="ld-mc-parada-val">{machine.status_parada}</span>
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

// ── página principal ─────────────────────────────────────────────────────────

export default function LinhaDetalhe() {
  const { lineId } = useParams();
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);
  const [metrica, setMetrica] = useState("OEE");

  const wsRef         = useRef(null);
  const retryRef      = useRef(0);
  const retryTimerRef = useRef(null);
  const aliveRef      = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    setData(null);
    setError(null);

    fetch(`${API_BASE}/api/lines/${lineId}/detail`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));

    const connect = () => {
      if (!aliveRef.current) return;
      const ws = new WebSocket(`${WS_BASE}/api/lines/${lineId}/ws`);
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
  }, [lineId]);

  if (error) return <div className="ld-error">Erro: {error}</div>;
  if (!data) return <div className="ld-loading"><div className="ld-spinner" />Carregando...</div>;

  const { kpis } = data;
  const oeeC = oeeColor(kpis.oee_global);

  return (
    <div className="ld-root">

      {/* ── Cabeçalho da página ──────────────────────────── */}
      <div className="ld-page-header">
        <div className="ld-page-header-left">
          <h1 className="ld-page-title">Monitoramento {data.nome}</h1>
          <div className="ld-page-sub">
            <span className="ld-status-dot" />
            <span>{data.status_geral}</span>
            <span className="ld-sep">•</span>
            <span>Última atualização: {data.ultima_atualizacao}</span>
          </div>
        </div>
        <div className="ld-page-header-right">
          <button className="ld-btn-secondary" type="button">
            <span>↓</span> Exportar Dados
          </button>
          <button className="ld-btn-primary" type="button">
            + Nova Ordem
          </button>
        </div>
      </div>

      {/* ── KPI cards ────────────────────────────────────── */}
      <div className="ld-kpi-grid">
        <KpiCard label="OEE Global da Linha" accent={oeeC}>
          <div className="ld-kpi-oee">
            <span className="ld-kpi-oee-val" style={{ color: oeeC }}>{kpis.oee_global}%</span>
            <span
              className="ld-kpi-oee-var"
              style={{ color: kpis.oee_variacao >= 0 ? "#16a34a" : "#dc2626" }}
            >
              {kpis.oee_variacao >= 0 ? "+" : ""}{kpis.oee_variacao}%
            </span>
          </div>
          <div className="ld-kpi-mini-bar">
            <div style={{ width: `${kpis.oee_global}%`, background: oeeC }} />
          </div>
        </KpiCard>

        <KpiCard label="Produção Hoje (Un)">
          <div className="ld-kpi-prod">
            <span className="ld-kpi-prod-val">
              {kpis.producao_hoje.toLocaleString("pt-BR")}
            </span>
            <span className="ld-kpi-prod-meta">
              / {kpis.producao_meta.toLocaleString("pt-BR")} Meta
            </span>
          </div>
          <div className="ld-kpi-previsao">
            Previsão de término: <strong>{kpis.previsao_termino}</strong>
          </div>
        </KpiCard>

        <KpiCard label="Máquinas Ativas">
          <div className="ld-kpi-maq">
            <span className="ld-kpi-maq-val">{kpis.maquinas_ativas}</span>
            <span className="ld-kpi-maq-sep">/</span>
            <span className="ld-kpi-maq-total">{kpis.maquinas_total}</span>
          </div>
          <div className="ld-kpi-maq-label">
            {kpis.maquinas_total - kpis.maquinas_ativas} em parada ou manutenção
          </div>
        </KpiCard>

        <KpiCard label="Equipe no Turno">
          <div className="ld-kpi-equipe">
            <div className="ld-avatar-stack">
              {kpis.equipe.map((m, i) => (
                <Avatar key={i} iniciais={m.iniciais} cor={m.cor} size={34} />
              ))}
              {kpis.equipe_extras > 0 && (
                <div className="ld-avatar ld-avatar-extra" style={{ width: 34, height: 34 }}>
                  +{kpis.equipe_extras}
                </div>
              )}
            </div>
          </div>
          <div className="ld-kpi-supervisor">Supervisor: {kpis.supervisor}</div>
        </KpiCard>
      </div>

      {/* ── Grid de máquinas ─────────────────────────────── */}
      <div className="ld-machines-section">
        <div className="ld-machines-header">
          <h2 className="ld-machines-title">Status das Máquinas</h2>
          <div className="ld-tab-group">
            {["OEE", "Disponibilidade", "Desempenho"].map((m) => (
              <button
                key={m}
                type="button"
                className={"ld-tab" + (metrica === m ? " active" : "")}
                onClick={() => setMetrica(m)}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <div className="ld-machine-grid">
          {data.maquinas.map((m) => (
            <MachineCard key={m.id} machine={m} metrica={metrica} />
          ))}
        </div>
      </div>
    </div>
  );
}