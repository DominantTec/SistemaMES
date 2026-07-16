import {
  ComposedChart, Bar, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea, Legend,
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

// Pontos desenhados à mão: o <Scatter> do recharts tira o raio do ZAxis, não de uma prop,
// então dois Scatter num mesmo gráfico saem do mesmo tamanho e o de cima apaga o de baixo.
// A câmara é o disco maior; a amostra é o disco menor por cima, com anel da cor do fundo
// para se destacar onde as duas coincidem (que é quase o ensaio inteiro).
const PontoCamara = ({ cx, cy }) =>
  cx == null || cy == null ? null : <circle cx={cx} cy={cy} r={4.5} fill="#ea580c" />;

const PontoAmostra = ({ cx, cy }) =>
  cx == null || cy == null ? null : (
    <circle cx={cx} cy={cy} r={2.2} fill="#0891b2" stroke="#ffffff" strokeWidth={1} />
  );

// Anotações sobre o eixo do tempo. Repetidas nos dois painéis (só um deles rotula, para o
// texto não sair duplicado) — é o que costura os dois plots num gráfico só.
const Faixa = ({ combustao, yAxisId, comLabel }) =>
  combustao && combustao.fim > combustao.inicio ? (
    <ReferenceArea
      yAxisId={yAxisId} x1={combustao.inicio} x2={combustao.fim}
      fill={ETAPAS[2].cor} fillOpacity={0.08} stroke="none"
      label={comLabel ? {
        value: `◀ Combustão · ${mmss(combustao.fim - combustao.inicio)} ▶`,
        position: "insideTop", fontSize: 10, fill: ETAPAS[2].cor,
      } : undefined}
    />
  ) : null;

const Ventoinhas = ({ ventos, yAxisId, comLabel }) => (
  <>
    {ventos.map((t, i) => (
      <ReferenceLine
        key={`v${i}`} yAxisId={yAxisId} x={t}
        stroke="#6b7280" strokeDasharray="3 3" strokeOpacity={0.8}
        label={comLabel ? {
          value: "❋ ventoinha", position: "insideBottomLeft",
          fontSize: 10, fill: "#6b7280",
        } : undefined}
      />
    ))}
  </>
);

const TooltipPeso = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="fv-chart-tooltip">
      <div className="fv-tt-x">{mmss(d.t)} de ensaio</div>
      <div className="fv-tt-massa">{fmt(d.queimado, 2)} g queimados</div>
      <div className="fv-tt-pot">restam {fmt(d.peso, 2)} g na balança</div>
    </div>
  );
};

const TooltipTemp = ({ active, payload }) => {
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

// Reamostra a curva para ~48 instantes. A API entrega até 400 pontos: cabem numa linha,
// mas não em barras (a ~700px sairiam barras de 1,7px, um bloco chapado) nem em pontos
// legíveis. Barra e ponto saem da MESMA amostra — cada instante tem uma barra e um ponto.
const MAX_AMOSTRAS = 48;

function reamostrar(curva, alvo = MAX_AMOSTRAS) {
  if (curva.length <= alvo) return curva;
  const passo = (curva.length - 1) / (alvo - 1);
  return Array.from({ length: alvo }, (_, i) => curva[Math.round(i * passo)]);
}

// Dois painéis empilhados sobre o MESMO eixo de tempo, em vez de um plot com dois eixos Y.
// Peso (g) e temperatura (°C) não têm escala comum: sobrepostos, o alinhamento entre as
// duas escalas seria arbitrário e o gráfico inventaria uma correlação que não está no dado.
// Empilhados, cada grandeza tem seu eixo honesto e o tempo continua compartilhado — a
// queima ainda se lê na vertical, e as anotações atravessam os dois painéis.
function CurvaEnsaio({ curva, setpoint, etapas, ventoinhaOn, pesoInicial }) {
  if (!curva?.length) {
    return <div className="fv-chart-empty">Inicie o ensaio no twin 3D para ver a curva.</div>;
  }

  const pesos = curva.map((p) => p.peso).filter((v) => v != null);
  const p0 = pesoInicial ?? (pesos.length ? Math.max(...pesos) : null);

  // A barra mede o betume JÁ QUEIMADO (0 -> ~35 g), não o peso restante. Comprimento de
  // barra só é honesto a partir do zero, e o peso restante não tem zero útil: numa base
  // truncada em 465 g uma perda de 7% pareceria perda total, e numa base 0..500 g a queima
  // sumiria. Invertida, a medida ganha zero real — e é o próprio resultado do ensaio.
  const amostras = reamostrar(curva).map((p) => ({
    ...p,
    queimado: p0 != null && p.peso != null ? Math.max(0, Number((p0 - p.peso).toFixed(2))) : null,
  }));

  const tMax = amostras[amostras.length - 1]?.t ?? 0;
  const dominioT = [0, tMax || "dataMax"];
  const eixoY = { width: 46 };
  const margem = { top: 8, right: 16, left: 4 };

  // Anotações. A combustão NÃO é a etapa 2 sozinha: o mock passa para o patamar ainda
  // queimando e só declara a etapa 4 quando o betume esgota (mock_clp_forno.py, "FIM DO
  // ENSAIO"). A faixa vai então do início da queima até o ensaio concluir — enquanto não
  // concluiu, ainda está queimando e a faixa segue até o fim dos dados. As marcas da
  // ventoinha vêm da API (detectadas antes do downsample). Tudo em tinta neutra ou na cor
  // da própria etapa: são eventos, não séries.
  const eQueima = (etapas || []).find((e) => e.etapa === 2);
  const eConcl  = (etapas || []).find((e) => e.etapa === 4);
  const combustao = eQueima
    ? { inicio: eQueima.inicio, fim: eConcl ? eConcl.inicio : tMax }
    : null;
  const ventos = (ventoinhaOn || []).filter((t) => t >= 0 && t <= tMax);

  return (
    <div className="fv-chart-stack">
      {/* Painel 1 — peso: só barras, saindo do zero */}
      <div className="fv-chart-panel">
        <div className="fv-chart-cap" style={{ color: "#16a34a" }}>Betume queimado (g)</div>
        <ResponsiveContainer width="100%" height={148}>
          <ComposedChart data={amostras} syncId="fv-ensaio" margin={{ ...margem, bottom: 0 }}>
            <CartesianGrid stroke="#f3f4f6" vertical={false} />
            <XAxis dataKey="t" type="number" domain={dominioT} tick={false}
                   axisLine={false} tickLine={false} height={0} />
            <YAxis yAxisId="peso" {...eixoY} domain={[0, "auto"]}
                   tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false}
                   tickFormatter={(v) => fmt(v, 0)} />
            <Tooltip content={<TooltipPeso />} cursor={{ fill: "#11182708" }} />
            <Faixa combustao={combustao} yAxisId="peso" comLabel />
            <Ventoinhas ventos={ventos} yAxisId="peso" />
            <Bar yAxisId="peso" dataKey="queimado" name="betume queimado (g)"
                 fill="#16a34a" radius={[4, 4, 0, 0]} maxBarSize={11} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Painel 2 — temperatura: só pontos, sem nenhuma linha ligando.
          Câmara com ponto maior e amostra menor por cima: as duas curvas quase coincidem
          (a amostra segue a câmara com ~15 s de atraso num ensaio de ~55 min), então com
          pontos do mesmo tamanho a de cima apagaria a de baixo. */}
      <div className="fv-chart-panel">
        <div className="fv-chart-cap" style={{ color: "#ea580c" }}>Temperatura (°C)</div>
        <ResponsiveContainer width="100%" height={214}>
          <ComposedChart data={amostras} syncId="fv-ensaio" margin={{ ...margem, bottom: 24 }}>
            <CartesianGrid stroke="#f3f4f6" vertical={false} />
            <XAxis dataKey="t" type="number" domain={dominioT}
                   tick={{ fontSize: 11, fill: "#9ca3af" }}
                   axisLine={false} tickLine={false} tickFormatter={mmss}
                   label={{ value: "Tempo de ensaio (mm:ss)", position: "insideBottom",
                            offset: -14, fontSize: 11, fill: "#6b7280" }} />
            <YAxis yAxisId="temp" {...eixoY} domain={[0, "auto"]}
                   tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
            <Tooltip content={<TooltipTemp />} cursor={{ stroke: "#d1d5db", strokeWidth: 1 }} />
            <Legend verticalAlign="top" align="right" height={22}
                    wrapperStyle={{ fontSize: 11 }} />
            <Faixa combustao={combustao} yAxisId="temp" />
            <Ventoinhas ventos={ventos} yAxisId="temp" comLabel />
            {setpoint > 0 && (
              <ReferenceLine
                yAxisId="temp" y={setpoint} stroke="#dc2626" strokeDasharray="5 4"
                label={{ value: `setpoint ${fmt(setpoint, 0)} °C`, position: "insideBottomRight",
                         fontSize: 10, fill: "#dc2626" }}
              />
            )}
            <Scatter yAxisId="temp" dataKey="camara" name="câmara (°C)"
                     fill="#ea580c" shape={<PontoCamara />} isAnimationActive={false} />
            <Scatter yAxisId="temp" dataKey="amostra" name="amostra (°C)"
                     fill="#0891b2" shape={<PontoAmostra />} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
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

      {/* Curva do ensaio: peso e temperatura no mesmo tempo */}
      <div className="md-card">
        <div className="md-card-title">
          Betume queimado e temperatura × tempo
          <span className="md-card-title-sub">
            {atual?.concluido ? "ensaio concluído — betume esgotado"
              : atual?.rodando ? "ao vivo" : "último ensaio"}
          </span>
        </div>
        <CurvaEnsaio
          curva={forno?.curva}
          setpoint={atual?.setpoint_c}
          etapas={forno?.etapas}
          ventoinhaOn={forno?.ventoinha_on}
          pesoInicial={atual?.peso_inicial_g}
        />
      </div>

      {/* Balança */}
      <Balanca atual={atual} />

    </div>
  );
}
