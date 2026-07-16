import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceDot,
} from "recharts";
import "./EnsaioView.css";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(v, dec = 1) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return Number(v).toLocaleString("pt-BR", {
    minimumFractionDigits: dec, maximumFractionDigits: dec,
  });
}

function estadoEnsaio(atual) {
  if (!atual) return { label: "SEM DADOS", color: "#6b7280", bg: "#f3f4f6", pulse: false };
  if (atual.ruptura)  return { label: "ROMPIDO",   color: "#dc2626", bg: "#fee2e2", pulse: false };
  if (atual.rodando)  return { label: "ENSAIANDO", color: "#16a34a", bg: "#dcfce7", pulse: true };
  return { label: "OCIOSO", color: "#6b7280", bg: "#f3f4f6", pulse: false };
}

const MODO_COR = { 1: "#2563eb", 2: "#7c3aed" };

// ── card de resultado ─────────────────────────────────────────────────────────

function ResultCard({ label, value, unit, color, dec = 1, destaque }) {
  return (
    <div className={`ev-card${destaque ? " ev-card-destaque" : ""}`} style={{ borderTop: `3px solid ${color}` }}>
      <div className="ev-card-label">{label}</div>
      <div className="ev-card-value" style={{ color }}>
        {fmt(value, dec)}
        {unit && <span className="ev-card-unit"> {unit}</span>}
      </div>
    </div>
  );
}

// ── curva Força × Deslocamento ────────────────────────────────────────────────

function CurvaEnsaio({ curva, forcaMax }) {
  if (!curva?.length) {
    return <div className="ev-chart-empty">Inicie um ensaio para ver a curva força × deslocamento.</div>;
  }

  // ponto de força máxima (marcador)
  let pico = null;
  for (const p of curva) if (!pico || p.forca > pico.forca) pico = p;

  const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="ev-chart-tooltip">
        <div className="ev-tt-x">{fmt(d.desloc, 2)} mm</div>
        <div className="ev-tt-forca">{fmt(d.forca, 1)} N</div>
        <div className="ev-tt-tensao">{fmt(d.tensao, 2)} MPa</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={curva} margin={{ top: 10, right: 20, left: 0, bottom: 18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="desloc" type="number"
          domain={[0, "dataMax"]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => `${fmt(v, 1)}`}
          label={{ value: "Deslocamento (mm)", position: "insideBottom", offset: -8, fontSize: 11, fill: "#6b7280" }}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          label={{ value: "Força (N)", angle: -90, position: "insideLeft", fontSize: 11, fill: "#6b7280" }}
        />
        <Tooltip content={<ChartTooltip />} />
        <Line
          type="monotone" dataKey="forca"
          stroke="#2563eb" strokeWidth={2.5}
          dot={{ r: 2.5, fill: "#2563eb" }} activeDot={{ r: 5 }}
          isAnimationActive={false}
        />
        {pico && pico.forca > 0 && (
          <ReferenceDot
            x={pico.desloc} y={pico.forca} r={5}
            fill="#dc2626" stroke="white" strokeWidth={2}
            label={{ value: `Fmáx ${fmt(forcaMax ?? pico.forca, 0)} N`, position: "top", fontSize: 10, fill: "#dc2626" }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── corpo da tela de Ensaio ───────────────────────────────────────────────────

export default function EnsaioView({ data }) {
  const ensaio = data.ensaio;
  const atual  = ensaio?.atual;
  const est    = estadoEnsaio(atual);
  const modoCor = MODO_COR[atual?.modo] || "#6b7280";

  return (
    <div className="ev-root">

      {/* Faixa de estado + macros do ensaio */}
      <div className="ev-status-strip">
        <div className="ev-status-main">
          <span className="ev-status-badge" style={{ color: est.color, background: est.bg }}>
            <span className={`ev-status-dot${est.pulse ? " ev-status-dot-pulse" : ""}`} style={{ background: est.color }} />
            {est.label}
          </span>
          {atual && (
            <span className="ev-modo-tag" style={{ color: modoCor, borderColor: modoCor }}>
              Ensaio de {atual.modo_label}
            </span>
          )}
        </div>

        <div className="ev-macros">
          <div className="ev-macro">
            <span className="ev-macro-label">Deslocamento</span>
            <span className="ev-macro-value">{fmt(atual?.deslocamento_mm, 2)}<small> mm</small></span>
          </div>
          <div className="ev-macro">
            <span className="ev-macro-label">Força atual</span>
            <span className="ev-macro-value">{fmt(atual?.forca_n, 0)}<small> N</small></span>
          </div>
          <div className="ev-macro">
            <span className="ev-macro-label">Ensaios (6h)</span>
            <span className="ev-macro-value">{ensaio?.ensaios_janela ?? 0}</span>
          </div>
        </div>
      </div>

      {/* Cards de resultado do ensaio */}
      <div className="ev-cards">
        <ResultCard label="FORÇA MÁXIMA"   value={atual?.forca_max_n}     unit="N"   color="#4f46e5" dec={0} destaque />
        <ResultCard label="TENSÃO"          value={atual?.tensao_mpa}      unit="MPa" color="#0891b2" dec={2} />
        <ResultCard label="MÓDULO DE ELASTICIDADE" value={atual?.modulo_mpa} unit="MPa" color="#7c3aed" dec={0} />
        <ResultCard label="ALONGAMENTO"     value={atual?.alongamento_pct} unit="%"   color="#d97706" dec={2} />
        <ResultCard
          label="R² (CORRELAÇÃO)"
          value={atual?.r2} dec={3}
          color={atual && atual.r2 >= 0.99 ? "#16a34a" : "#dc2626"}
        />
        <ResultCard label="FORÇA ATUAL"     value={atual?.forca_n}         unit="N"   color="#2563eb" dec={0} />
      </div>

      {/* Curva do ensaio */}
      <div className="md-card">
        <div className="md-card-title">
          Curva Força × Deslocamento
          <span className="md-card-title-sub">
            {atual?.ruptura ? "ensaio concluído — rompeu" : atual?.rodando ? "ao vivo" : "último ensaio"}
          </span>
        </div>
        <CurvaEnsaio curva={ensaio?.curva} forcaMax={atual?.forca_max_n} />
      </div>

    </div>
  );
}
