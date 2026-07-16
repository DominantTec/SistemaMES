import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import "./FornoView.css";

// Etapas do ensaio (vêm do CLP em D4; só avançam). Cor por etapa é usada tanto na
// linha do tempo quanto no badge de estado.
const ETAPAS = {
  0: { label: "Ocioso",           cor: "#6b7280" },
  1: { label: "Aquecimento",      cor: "#ea580c" },
  2: { label: "Queima do betume", cor: "#d97706" },
  3: { label: "Patamar 540 °C",   cor: "#dc2626" },
  4: { label: "Concluído",        cor: "#16a34a" },
  5: { label: "Resfriamento",     cor: "#0891b2" },
};

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(v, dec = 1) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return Number(v).toLocaleString("pt-BR", {
    minimumFractionDigits: dec, maximumFractionDigits: dec,
  });
}

function estadoForno(atual) {
  if (!atual) return { label: "SEM DADOS", color: "#6b7280", bg: "#f3f4f6", pulse: false };
  const e = ETAPAS[atual.etapa] || ETAPAS[0];
  const bg = {
    0: "#f3f4f6", 1: "#ffedd5", 2: "#fef3c7", 3: "#fee2e2", 4: "#dcfce7", 5: "#cffafe",
  }[atual.etapa] || "#f3f4f6";
  return {
    label: e.label.toUpperCase(),
    color: e.cor,
    bg,
    pulse: atual.etapa >= 1 && atual.etapa <= 3,   // pulsa só enquanto o ensaio corre
  };
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

// ── linha do tempo das etapas ─────────────────────────────────────────────────

function LinhaDoTempo({ etapas, atual }) {
  if (!etapas?.length) {
    return <div className="fv-chart-empty">Inicie o ensaio no twin 3D para acompanhar as etapas.</div>;
  }

  // a barra mede do início da 1ª etapa até agora — o ensaio pode ter começado
  // alguns segundos depois do relógio zerar
  const base = etapas[0].inicio;
  const fim = etapas[etapas.length - 1].fim;
  const total = Math.max(fim - base, 1);
  const emAndamento = atual?.etapa;
  // Etapas do ensaio que ainda não aconteceram: mostradas apagadas, para dar a
  // noção de "o que falta" além do "por onde passou".
  const previstas = [1, 2, 3, 4].filter((e) => !etapas.some((s) => s.etapa === e));

  return (
    <div className="md-card">
      <div className="md-card-title">
        Etapas do ensaio
        <span className="md-card-title-sub">
          {atual?.concluido ? `concluído em ${mmss(total)}` : `em andamento — ${mmss(total)}`}
        </span>
      </div>

      <div className="fv-tl-head">
        {atual?.concluido
          ? "O ensaio terminou sozinho: o Δpeso chegou a zero, ou seja, o betume acabou."
          : "As etapas se formam conforme o ensaio corre. Ele termina quando o Δpeso zerar."}
      </div>

      <div className="fv-tl">
        <div className="fv-tl-bar">
          {etapas.map((s, i) => {
            const largura = (s.duracao / total) * 100;
            const cor = (ETAPAS[s.etapa] || ETAPAS[0]).cor;
            const ativa = s.etapa === emAndamento && !atual?.concluido;
            return (
              <div
                key={i}
                className={`fv-tl-seg${ativa ? " fv-tl-seg-ativa" : ""}`}
                style={{ width: `${largura}%`, background: cor }}
                title={`${s.label}: ${mmss(s.inicio - base)} → ${mmss(s.fim - base)} (${mmss(s.duracao)})`}
              >
                {largura > 12 && <span className="fv-tl-seg-txt">{s.label}</span>}
              </div>
            );
          })}
        </div>

        <div className="fv-tl-eixo">
          <span>0:00</span>
          <span>{mmss(total)}</span>
        </div>
        {/* eixo relativo ao início do ensaio (base), não ao relógio do CLP */}

        <div className="fv-tl-legenda">
          {etapas.map((s, i) => (
            <span key={i} className="fv-tl-item">
              <i style={{ background: (ETAPAS[s.etapa] || ETAPAS[0]).cor }} />
              {s.label}
              <small>{mmss(s.duracao)}</small>
            </span>
          ))}
          {previstas.map((e) => (
            <span key={`p${e}`} className="fv-tl-item fv-tl-item-futura">
              <i style={{ background: "#d1d5db" }} />
              {ETAPAS[e].label}
              <small>—</small>
            </span>
          ))}
        </div>
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
        Balança — teor de betume
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
            <span className="fv-bal-label">Teor de betume</span>
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
          <span><i style={{ background: "#16a34a" }} />agregado (massa retida)</span>
          <span><i style={{ background: "#f59e0b" }} />betume queimado</span>
        </div>
      </div>
    </div>
  );
}

// ── curva de aquecimento ──────────────────────────────────────────────────────

// Três eixos: tempo embaixo, temperatura à esquerda, peso à direita. As duas
// grandezas do ensaio no mesmo tempo — dá pra ver o peso despencar exatamente
// quando a temperatura cruza a faixa de queima do betume.
function CurvaEnsaio({ curva, setpoint, etapas }) {
  if (!curva?.length) {
    return <div className="fv-chart-empty">Inicie o ensaio no twin 3D para ver a curva.</div>;
  }

  // eixo do peso "colado" na faixa útil: sem isso a queda de 7% vira uma linha reta
  const pesos = curva.map((p) => p.peso).filter((v) => v != null);
  const pMin = pesos.length ? Math.min(...pesos) : 0;
  const pMax = pesos.length ? Math.max(...pesos) : 1;
  const folga = Math.max((pMax - pMin) * 0.25, 0.5);
  const dominioPeso = [
    Math.floor((pMin - folga) * 10) / 10,
    Math.ceil((pMax + folga) * 10) / 10,
  ];

  const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="fv-chart-tooltip">
        <div className="fv-tt-x">{mmss(d.t)} de ensaio</div>
        <div className="fv-tt-camara">câmara {fmt(d.camara, 1)} °C</div>
        <div className="fv-tt-amostra">amostra {fmt(d.amostra, 1)} °C</div>
        <div className="fv-tt-massa">peso {fmt(d.peso, 2)} g</div>
        <div className="fv-tt-pot">{fmt(d.potencia, 0)} W</div>
      </div>
    );
  };

  // marca onde cada etapa começou, para casar o gráfico com a linha do tempo
  const marcos = (etapas || []).filter((e) => e.etapa >= 2 && e.inicio > 0);

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={curva} margin={{ top: 10, right: 12, left: 0, bottom: 22 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="t" type="number" domain={[0, "dataMax"]}
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false} tickLine={false}
          tickFormatter={mmss}
          label={{ value: "Tempo de ensaio (mm:ss)", position: "insideBottom", offset: -10, fontSize: 11, fill: "#6b7280" }}
        />
        <YAxis
          yAxisId="temp" orientation="left"
          tick={{ fontSize: 11, fill: "#ea580c" }}
          axisLine={false} tickLine={false}
          label={{ value: "Temperatura (°C)", angle: -90, position: "insideLeft", fontSize: 11, fill: "#ea580c" }}
        />
        <YAxis
          yAxisId="peso" orientation="right" domain={dominioPeso}
          tick={{ fontSize: 11, fill: "#16a34a" }}
          axisLine={false} tickLine={false}
          tickFormatter={(v) => fmt(v, 1)}
          label={{ value: "Peso (g)", angle: 90, position: "insideRight", fontSize: 11, fill: "#16a34a" }}
        />
        <Tooltip content={<ChartTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} />

        {setpoint > 0 && (
          <ReferenceLine
            yAxisId="temp" y={setpoint} stroke="#dc2626" strokeDasharray="5 4"
            label={{ value: `setpoint ${fmt(setpoint, 0)} °C`, position: "insideTopRight", fontSize: 10, fill: "#dc2626" }}
          />
        )}
        {marcos.map((m, i) => (
          <ReferenceLine
            key={i} yAxisId="temp" x={m.inicio}
            stroke={(ETAPAS[m.etapa] || ETAPAS[0]).cor} strokeDasharray="2 3" strokeOpacity={0.6}
          />
        ))}

        <Line yAxisId="temp" type="monotone" dataKey="camara"  name="câmara (°C)"
              stroke="#ea580c" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        <Line yAxisId="temp" type="monotone" dataKey="amostra" name="amostra (°C)"
              stroke="#0891b2" strokeWidth={1.8} dot={false} isAnimationActive={false} strokeDasharray="4 3" />
        <Line yAxisId="peso" type="monotone" dataKey="peso"    name="peso (g)"
              stroke="#16a34a" strokeWidth={2.5} dot={false} isAnimationActive={false} />
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
        <ResultCard label="TEOR DE BETUME"   value={atual?.perda_massa_pct} unit="%"  color="#d97706" dec={2} destaque />
        <ResultCard label="TEMP. DA AMOSTRA" value={atual?.temp_amostra_c} unit="°C" color="#0891b2" dec={1} />
        <ResultCard label="POTÊNCIA"         value={atual?.potencia_w}     unit="W"  color="#dc2626" dec={0} />
        <ResultCard label="ENERGIA FORNECIDA" value={atual?.energia_kj}    unit="kJ" color="#7c3aed" dec={0} />
        <ResultCard label="PESO ATUAL"       value={atual?.peso_atual_g}   unit="g"  color="#16a34a" dec={1} />
        <ResultCard label="TAXA DE QUEIMA"   value={atual ? atual.taxa_betume * 100 : null} unit="%" color="#6b7280" dec={0} />
      </div>

      {/* Linha do tempo das etapas */}
      <LinhaDoTempo etapas={forno?.etapas} atual={atual} />

      {/* Curva do ensaio: temperatura e peso no mesmo tempo */}
      <div className="md-card">
        <div className="md-card-title">
          Temperatura e peso × tempo
          <span className="md-card-title-sub">
            {atual?.concluido ? "ensaio concluído — betume esgotado"
              : atual?.rodando ? "ao vivo" : "último ensaio"}
          </span>
        </div>
        <CurvaEnsaio curva={forno?.curva} setpoint={atual?.setpoint_c} etapas={forno?.etapas} />
      </div>

      {/* Balança */}
      <Balanca atual={atual} />

    </div>
  );
}
