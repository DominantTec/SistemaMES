import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import "./FornoView.css";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(v, dec = 1) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return Number(v).toLocaleString("pt-BR", {
    minimumFractionDigits: dec, maximumFractionDigits: dec,
  });
}

function estadoForno(atual) {
  if (!atual) return { label: "SEM DADOS", color: "#6b7280", bg: "#f3f4f6", pulse: false };
  if (atual.patamar)          return { label: "EM PATAMAR",  color: "#dc2626", bg: "#fee2e2", pulse: true };
  if (atual.rodando)          return { label: "AQUECENDO",   color: "#ea580c", bg: "#ffedd5", pulse: true };
  if (atual.modo === 3)       return { label: "RESFRIANDO",  color: "#0891b2", bg: "#cffafe", pulse: false };
  return { label: "OCIOSO", color: "#6b7280", bg: "#f3f4f6", pulse: false };
}

// tempo de ensaio (s) -> mm:ss
function mmss(s) {
  if (s === null || s === undefined || isNaN(s)) return "—";
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

// ── card de resultado ─────────────────────────────────────────────────────────

function ResultCard({ label, value, unit, color, dec = 1, destaque }) {
  return (
    <div className={`fv-card${destaque ? " fv-card-destaque" : ""}`} style={{ borderTop: `3px solid ${color}` }}>
      <div className="fv-card-label">{label}</div>
      <div className="fv-card-value" style={{ color }}>
        {fmt(value, dec)}
        {unit && <span className="fv-card-unit"> {unit}</span>}
      </div>
    </div>
  );
}

// ── comparativo da balança ────────────────────────────────────────────────────

function Balanca({ atual }) {
  const ini = atual?.peso_inicial_g ?? 0;
  const at  = atual?.peso_atual_g ?? 0;
  const perdido = atual?.peso_perdido_g ?? 0;
  const pct = atual?.perda_massa_pct ?? 0;
  const retidoPct = ini > 0 ? Math.max(0, Math.min((at / ini) * 100, 100)) : 100;

  return (
    <div className="md-card">
      <div className="md-card-title">
        Balança — perda ao fogo
        <span className="md-card-title-sub">peso inicial × peso atual</span>
      </div>

      <div className="fv-bal">
        <div className="fv-bal-nums">
          <div className="fv-bal-item">
            <span className="fv-bal-label">Peso inicial</span>
            <span className="fv-bal-value">{fmt(ini, 1)}<small> g</small></span>
          </div>
          <div className="fv-bal-arrow">→</div>
          <div className="fv-bal-item">
            <span className="fv-bal-label">Peso atual</span>
            <span className="fv-bal-value fv-bal-atual">{fmt(at, 1)}<small> g</small></span>
          </div>
          <div className="fv-bal-item fv-bal-delta">
            <span className="fv-bal-label">Perdeu</span>
            <span className="fv-bal-value" style={{ color: "#d97706" }}>
              −{fmt(perdido, 1)}<small> g</small>
            </span>
          </div>
          <div className="fv-bal-item">
            <span className="fv-bal-label">Perda</span>
            <span className="fv-bal-value" style={{ color: "#d97706" }}>
              {fmt(pct, 2)}<small> %</small>
            </span>
          </div>
        </div>

        {/* barra: massa retida (verde) sobre o total inicial (âmbar = perdido) */}
        <div className="fv-bal-bar" title={`${fmt(retidoPct, 1)}% da massa inicial`}>
          <div className="fv-bal-bar-fill" style={{ width: `${retidoPct}%` }} />
        </div>
        <div className="fv-bal-legend">
          <span><i style={{ background: "#16a34a" }} />massa retida</span>
          <span><i style={{ background: "#f59e0b" }} />massa perdida (voláteis)</span>
        </div>
      </div>
    </div>
  );
}

// ── curva de aquecimento ──────────────────────────────────────────────────────

function CurvaAquecimento({ curva, setpoint }) {
  if (!curva?.length) {
    return <div className="fv-chart-empty">Inicie o ensaio no twin 3D para ver a curva de aquecimento.</div>;
  }

  const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="fv-chart-tooltip">
        <div className="fv-tt-x">{mmss(d.t)} de ensaio</div>
        <div className="fv-tt-camara">câmara {fmt(d.camara, 1)} °C</div>
        <div className="fv-tt-amostra">amostra {fmt(d.amostra, 1)} °C</div>
        <div className="fv-tt-pot">{fmt(d.potencia, 0)} W</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={curva} margin={{ top: 10, right: 20, left: 0, bottom: 18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="t" type="number" domain={[0, "dataMax"]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          tickFormatter={mmss}
          label={{ value: "Tempo de ensaio (mm:ss)", position: "insideBottom", offset: -8, fontSize: 11, fill: "#6b7280" }}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          label={{ value: "Temperatura (°C)", angle: -90, position: "insideLeft", fontSize: 11, fill: "#6b7280" }}
        />
        <Tooltip content={<ChartTooltip />} />
        {setpoint > 0 && (
          <ReferenceLine
            y={setpoint} stroke="#dc2626" strokeDasharray="5 4"
            label={{ value: `setpoint ${fmt(setpoint, 0)} °C`, position: "right", fontSize: 10, fill: "#dc2626" }}
          />
        )}
        <Line type="monotone" dataKey="camara"  stroke="#ea580c" strokeWidth={2.5} dot={false} isAnimationActive={false} name="câmara" />
        <Line type="monotone" dataKey="amostra" stroke="#0891b2" strokeWidth={2} dot={false} isAnimationActive={false} name="amostra" strokeDasharray="4 3" />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── curva TGA (massa × temperatura) ───────────────────────────────────────────

function CurvaTGA({ tga }) {
  if (!tga?.length) {
    return <div className="fv-chart-empty">Sem dados de massa ainda.</div>;
  }

  const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="fv-chart-tooltip">
        <div className="fv-tt-x">{fmt(d.temp, 0)} °C</div>
        <div className="fv-tt-massa">massa {fmt(d.massa_pct, 2)} %</div>
        <div className="fv-tt-pot">perda {fmt(d.perda_pct, 2)} %</div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={tga} margin={{ top: 10, right: 20, left: 0, bottom: 18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="temp" type="number" domain={["dataMin", "dataMax"]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => fmt(v, 0)}
          label={{ value: "Temperatura da amostra (°C)", position: "insideBottom", offset: -8, fontSize: 11, fill: "#6b7280" }}
        />
        <YAxis
          domain={["dataMin - 1", 100]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => fmt(v, 0)}
          label={{ value: "Massa retida (%)", angle: -90, position: "insideLeft", fontSize: 11, fill: "#6b7280" }}
        />
        <Tooltip content={<ChartTooltip />} />
        <Line type="monotone" dataKey="massa_pct" stroke="#16a34a" strokeWidth={2.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── corpo da tela do Forno Mufla ──────────────────────────────────────────────

export default function FornoView({ data }) {
  const forno = data.forno;
  const atual = forno?.atual;
  const est   = estadoForno(atual);
  const taxa  = forno?.taxa_c_min ?? 0;

  return (
    <div className="fv-root">

      {/* Faixa de estado + macros */}
      <div className="fv-status-strip">
        <div className="fv-status-main">
          <span className="fv-status-badge" style={{ color: est.color, background: est.bg }}>
            <span className={`fv-status-dot${est.pulse ? " fv-status-dot-pulse" : ""}`} style={{ background: est.color }} />
            {est.label}
          </span>
          {atual?.ventoinha && (
            <span className="fv-tag-vent">❋ Exaustão ligada</span>
          )}
        </div>

        <div className="fv-macros">
          <div className="fv-macro">
            <span className="fv-macro-label">Câmara</span>
            <span className="fv-macro-value">{fmt(atual?.temperatura_c, 1)}<small> °C</small></span>
          </div>
          <div className="fv-macro">
            <span className="fv-macro-label">Setpoint</span>
            <span className="fv-macro-value">{fmt(atual?.setpoint_c, 0)}<small> °C</small></span>
          </div>
          <div className="fv-macro">
            <span className="fv-macro-label">Taxa</span>
            <span className="fv-macro-value">{fmt(taxa, 1)}<small> °C/min</small></span>
          </div>
          <div className="fv-macro">
            <span className="fv-macro-label">Tempo de ensaio</span>
            <span className="fv-macro-value">{mmss(atual?.tempo_s)}</span>
          </div>
        </div>
      </div>

      {/* Cards */}
      <div className="fv-cards">
        <ResultCard label="PERDA DE MASSA"  value={atual?.perda_massa_pct} unit="%"  color="#d97706" dec={2} destaque />
        <ResultCard label="TEMP. DA AMOSTRA" value={atual?.temp_amostra_c} unit="°C" color="#0891b2" dec={1} />
        <ResultCard label="POTÊNCIA"         value={atual?.potencia_w}     unit="W"  color="#dc2626" dec={0} />
        <ResultCard label="ENERGIA FORNECIDA" value={atual?.energia_kj}    unit="kJ" color="#7c3aed" dec={0} />
        <ResultCard label="PESO ATUAL"       value={atual?.peso_atual_g}   unit="g"  color="#16a34a" dec={1} />
        <ResultCard label="LIBERAÇÃO DE VOLÁTEIS" value={atual ? atual.taxa_volateis * 100 : null} unit="%" color="#6b7280" dec={0} />
      </div>

      {/* Balança */}
      <Balanca atual={atual} />

      {/* Curva de aquecimento */}
      <div className="md-card">
        <div className="md-card-title">
          Curva de aquecimento
          <span className="md-card-title-sub">
            {atual?.patamar ? "em patamar" : atual?.rodando ? "ao vivo" : "último ensaio"}
          </span>
        </div>
        <CurvaAquecimento curva={forno?.curva} setpoint={atual?.setpoint_c} />
      </div>

      {/* TGA */}
      <div className="md-card">
        <div className="md-card-title">
          Perda de massa × temperatura (TGA)
          <span className="md-card-title-sub">massa retida conforme a amostra aquece</span>
        </div>
        <CurvaTGA tga={forno?.tga} />
      </div>

    </div>
  );
}
