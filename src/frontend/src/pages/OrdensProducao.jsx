import { useEffect, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import "./OrdensProducao.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE    = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE     = API_BASE.replace(/^http/, "ws");

const COLUNAS = [
  { id: "fila",        label: "Fila",         color: "#1f6feb" },
  { id: "em_producao", label: "Em Produção",   color: "#d97706" },
  { id: "finalizado",  label: "Finalizado",    color: "#16a34a" },
  { id: "cancelado",   label: "Cancelado",     color: "#6b7280" },
];

function fmtData(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })
    + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function badgePrioridade(p) {
  if (p >= 8) return { cls: "alta",   label: "Alta" };
  if (p >= 4) return { cls: "media",  label: "Média" };
  return             { cls: "normal", label: "Normal" };
}

// ---- Card (draggable) ----
function OPCard({ op, onDelete, isOverlay = false }) {
  const { attributes, listeners, setNodeRef, isDragging } =
    useDraggable({ id: op.id });

  const badge = badgePrioridade(op.prioridade);

  const classes = [
    "op-card",
    isDragging          ? "is-dragging" : "",
    isOverlay           ? "overlay"     : "",
    op.status === "cancelado" ? "is-cancelado" : "",
  ].filter(Boolean).join(" ");

  return (
    <div ref={setNodeRef} className={classes} {...listeners} {...attributes}>
      <div className="op-card-top">
        <span className="op-card-numero">{op.numero_op}</span>
        <div className="op-card-badges">
          {op.status === "em_producao" && (
            <span className="badge-producao-ativa" title="Em produção" />
          )}
          {op.prioridade > 0 && (
            <span className={`badge-prioridade ${badge.cls}`}>{badge.label}</span>
          )}
        </div>
      </div>

      <div className="op-card-linha">
        <span className="op-card-linha-dot" />
        {op.linha_nome}
      </div>

      <div className="op-card-peca">{op.peca || "—"}</div>

      <hr className="op-card-divider" />

      {op.status === "finalizado" ? (
        <div className="op-card-resultado">
          {(() => {
            const rendimento = op.quantidade > 0
              ? Math.round(100 * (op.produzido ?? 0) / op.quantidade)
              : 0;
            const corRendimento = rendimento >= 90 ? "#16a34a" : rendimento >= 70 ? "#d97706" : "#dc2626";
            return (
              <>
                <div className="op-card-rendimento" style={{ color: corRendimento }}>
                  {rendimento}% rendimento
                </div>
                <div className="op-card-info">
                  <div className="op-card-info-item">
                    <span className="op-card-info-label">Planejado</span>
                    <span className="op-card-info-value">{op.quantidade.toLocaleString("pt-BR")} un</span>
                  </div>
                  <div className="op-card-info-item">
                    <span className="op-card-info-label">Conformes</span>
                    <span className="op-card-info-value" style={{ color: "#16a34a" }}>{(op.produzido ?? 0).toLocaleString("pt-BR")} un</span>
                  </div>
                  {(op.refugo ?? 0) > 0 && (
                    <div className="op-card-info-item">
                      <span className="op-card-info-label">Refugo</span>
                      <span className="op-card-info-value" style={{ color: "#dc2626" }}>{op.refugo.toLocaleString("pt-BR")} un</span>
                    </div>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      ) : (
        <>
          <div className="op-card-info">
            <div className="op-card-info-item">
              <span className="op-card-info-label">Quantidade total</span>
              <span className="op-card-info-value">{op.quantidade.toLocaleString("pt-BR")} un</span>
            </div>
            <div className="op-card-info-item">
              <span className="op-card-info-label">Meta turno atual</span>
              <span className="op-card-info-value">{(op.meta_turno_atual ?? 0).toLocaleString("pt-BR")} un</span>
            </div>
          </div>
          {(op.pecas_proximos_turnos ?? 0) > 0 && (
            <div className="op-card-proximos-turnos">
              <span className="op-card-proximos-icon">⏭</span>
              <span>{(op.pecas_proximos_turnos).toLocaleString("pt-BR")} un em turnos futuros</span>
            </div>
          )}
        </>
      )}

      {op.observacoes && (
        <div className="op-card-obs" title={op.observacoes}>{op.observacoes}</div>
      )}

      <div className="op-card-footer">
        <span className="op-card-data">
          {op.status === "finalizado" && op.dt_fim
            ? `Finalizado ${fmtData(op.dt_fim)}`
            : op.status === "em_producao" && op.dt_inicio
            ? `Iniciado ${fmtData(op.dt_inicio)}`
            : `Criado ${fmtData(op.dt_criacao)}`}
        </span>
        {!isOverlay && (
          <button
            className="btn-del-op"
            title="Excluir OP"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); onDelete(op.id); }}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

// ---- Coluna (droppable) ----
function Coluna({ coluna, ordens, onDelete }) {
  const { setNodeRef, isOver } = useDroppable({ id: coluna.id });

  return (
    <div className={`op-coluna${isOver ? " is-over" : ""}`}>
      <div className="op-coluna-header">
        <span className="op-coluna-dot" style={{ background: coluna.color }} />
        <span className="op-coluna-titulo">{coluna.label}</span>
        <span className="op-coluna-count">{ordens.length}</span>
      </div>
      <div ref={setNodeRef} className="op-coluna-body">
        {ordens.length === 0 && (
          <div className="op-coluna-vazia">Nenhuma OP</div>
        )}
        {ordens.map((op) => (
          <OPCard key={op.id} op={op} onDelete={onDelete} />
        ))}
      </div>
    </div>
  );
}

// ---- Modal Nova OP ----
function NovaOPModal({ linhas, onClose, onSave }) {
  const [form, setForm] = useState({
    numero_op:   "",
    linha_id:    linhas[0]?.id ?? "",
    peca_id:     "",
    quantidade:  "",
    prioridade:  "0",
    observacoes: "",
  });
  const [pecas, setPecas]       = useState([]);
  const [loading, setLoading]   = useState(false);
  const [preview, setPreview]   = useState(null);
  const previewTimer            = useRef(null);

  // Busca próximo número ao abrir
  useEffect(() => {
    fetch(`${API_BASE}/api/ordens/proximo-numero`)
      .then((r) => r.json())
      .then((d) => setForm((f) => ({ ...f, numero_op: d.numero })))
      .catch(() => {});
  }, []);

  // Busca peças ao mudar linha
  useEffect(() => {
    if (!form.linha_id) return;
    setPecas([]);
    setForm((f) => ({ ...f, peca_id: "" }));
    fetch(`${API_BASE}/api/config/lines/${form.linha_id}/pecas`)
      .then((r) => r.json())
      .then((data) => {
        setPecas(data);
        if (data.length > 0) setForm((f) => ({ ...f, peca_id: data[0].id }));
      })
      .catch(() => {});
  }, [form.linha_id]);

  // Preview de metas: debounce 500ms ao mudar linha, peça ou quantidade
  useEffect(() => {
    clearTimeout(previewTimer.current);
    const qtd = Number(form.quantidade);
    if (!form.linha_id || !qtd || qtd <= 0) { setPreview(null); return; }
    previewTimer.current = setTimeout(() => {
      const params = `linha_id=${form.linha_id}&quantidade=${qtd}${form.peca_id ? `&peca_id=${form.peca_id}` : ""}`;
      fetch(`${API_BASE}/api/ordens/preview-metas?${params}`)
        .then((r) => r.json())
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 500);
    return () => clearTimeout(previewTimer.current);
  }, [form.linha_id, form.peca_id, form.quantidade]);

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSave() {
    if (!form.numero_op || !form.linha_id || !form.peca_id) return;
    setLoading(true);
    const pecaSelecionada = pecas.find(p => p.id === Number(form.peca_id));
    await onSave({
      numero_op:   form.numero_op,
      linha_id:    Number(form.linha_id),
      peca:        pecaSelecionada?.nome ?? "",
      peca_id:     Number(form.peca_id),
      quantidade:  Number(form.quantidade) || 0,
      prioridade:  Number(form.prioridade) || 0,
      observacoes: form.observacoes,
    });
    setLoading(false);
  }

  const valid = form.numero_op && form.linha_id && form.peca_id;

  return (
    <div className="op-modal-overlay" onClick={onClose}>
      <div className="op-modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="op-modal-titulo">Nova Ordem de Produção</h2>

        <div className="op-modal-grid">
          <div className="op-modal-field">
            <label>Número da OP</label>
            <input
              value={form.numero_op}
              onChange={(e) => set("numero_op", e.target.value)}
              placeholder="OP-YYYYMM-0001"
            />
          </div>

          <div className="op-modal-field">
            <label>Linha de Produção</label>
            <select value={form.linha_id} onChange={(e) => set("linha_id", e.target.value)}>
              {linhas.map((l) => (
                <option key={l.id} value={l.id}>{l.nome}</option>
              ))}
            </select>
          </div>

          <div className="op-modal-field full">
            <label>Peça / Produto</label>
            {pecas.length > 0 ? (
              <select value={form.peca_id} onChange={(e) => set("peca_id", e.target.value)}>
                {pecas.map((p) => (
                  <option key={p.id} value={p.id}>{p.nome}</option>
                ))}
              </select>
            ) : (
              <div className="op-modal-no-pecas">
                Nenhuma peça configurada para esta linha.
                Cadastre em Configurações → Peças e Roteiros.
              </div>
            )}
          </div>

          <div className="op-modal-field">
            <label>Quantidade total (un)</label>
            <input
              type="number"
              min="0"
              value={form.quantidade}
              onChange={(e) => set("quantidade", e.target.value)}
              placeholder="0"
            />
          </div>

          <div className="op-modal-field">
            <label>Prioridade (0–10)</label>
            <input
              type="number"
              min="0"
              max="10"
              value={form.prioridade}
              onChange={(e) => set("prioridade", e.target.value)}
              placeholder="0"
            />
          </div>

          <div className="op-modal-field full">
            <label>Observações</label>
            <textarea
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Instruções, notas..."
            />
          </div>
        </div>

        {/* Preview de distribuição por turno */}
        {preview && (
          <div className="op-modal-preview">
            <div className="op-modal-preview-title">Distribuição estimada por turno</div>
            <div className="op-modal-preview-row">
              <span className="op-preview-label">Meta turno atual</span>
              <span className="op-preview-value green">{preview.meta_turno_atual.toLocaleString("pt-BR")} un</span>
            </div>
            {preview.pecas_proximos_turnos > 0 && (
              <div className="op-modal-preview-row">
                <span className="op-preview-label">Turnos futuros</span>
                <span className="op-preview-value orange">{preview.pecas_proximos_turnos.toLocaleString("pt-BR")} un</span>
              </div>
            )}
            {preview.meta_turno_atual === 0 && (
              <p className="op-preview-aviso">
                Nenhum turno ativo no momento. As peças serão alocadas ao próximo turno disponível.
              </p>
            )}
          </div>
        )}

        <div className="op-modal-actions">
          <button className="btn-modal-cancel" onClick={onClose}>Cancelar</button>
          <button
            className="btn-modal-save"
            onClick={handleSave}
            disabled={!valid || loading}
          >
            {loading ? "Salvando..." : "Criar OP"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Mapa de Produção ----
const STATUS_CORES = {
  fila:        "#1f6feb",
  em_producao: "#d97706",
  finalizado:  "#16a34a",
  cancelado:   "#6b7280",
};
const STATUS_LABELS = {
  fila: "Fila", em_producao: "Em Produção", finalizado: "Finalizado", cancelado: "Cancelado",
};

function FluxogramaOP({ op, fluxo, onSave }) {
  // distribuicao local: { [tipo_maquina]: { [id_ihm]: percentual } }
  const [dist, setDist] = useState(() => {
    const d = {};
    (fluxo.steps || []).forEach(step => {
      d[step.tipo_maquina] = {};
      step.maquinas.forEach(m => { d[step.tipo_maquina][m.id_ihm] = m.percentual; });
    });
    return d;
  });
  const [saving, setSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);

  const hasParallel = (fluxo.steps || []).some(s => s.maquinas.length > 1);

  function handlePctChange(tipo, id_ihm, valor) {
    const num = Math.max(0, Math.min(100, Number(valor) || 0));
    setDist(prev => ({
      ...prev,
      [tipo]: { ...prev[tipo], [id_ihm]: num },
    }));
  }

  async function handleSave() {
    setSaving(true);
    const entries = [];
    (fluxo.steps || []).forEach(step => {
      step.maquinas.forEach(m => {
        entries.push({
          id_ihm:       m.id_ihm,
          tipo_maquina: step.tipo_maquina,
          percentual:   dist[step.tipo_maquina]?.[m.id_ihm] ?? m.percentual,
        });
      });
    });
    await fetch(`${API_BASE}/api/ordens/${op.id}/distribuicao`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entries),
    });
    setSaving(false);
    setSavedOk(true);
    setTimeout(() => setSavedOk(false), 2500);
    if (onSave) onSave();
  }

  return (
    <div className="fluxo-root">
      <div className="fluxo-scroll">
        {/* Nó de entrada */}
        <div className="fluxo-node fluxo-node--entrada">
          <div className="fluxo-node-label">Entrada</div>
          <div className="fluxo-node-qty">{op.quantidade.toLocaleString("pt-BR")} un</div>
        </div>

        {(fluxo.steps || []).map((step, i) => {
          const isParalelo = step.maquinas.length > 1;
          return (
            <div key={i} className="fluxo-step-wrap">
              <div className="fluxo-arrow">→</div>
              <div className={`fluxo-step${isParalelo ? " fluxo-step--paralelo" : ""}`}>
                <div className="fluxo-step-tipo">{step.tipo_maquina}</div>
                {step.producao_teorica > 0 && (
                  <div className="fluxo-step-teorica">{step.producao_teorica} pç/h</div>
                )}
                <div className="fluxo-maquinas">
                  {step.maquinas.map(m => {
                    const pct = dist[step.tipo_maquina]?.[m.id_ihm] ?? m.percentual;
                    const qty = Math.round(op.quantidade * pct / 100);
                    return (
                      <div key={m.id_ihm} className={`fluxo-maquina${pct === 0 ? " fluxo-maquina--inativa" : ""}`}>
                        <div className="fluxo-maquina-nome">{m.nome}</div>
                        {isParalelo ? (
                          <div className="fluxo-maquina-split">
                            <input
                              className="fluxo-pct-input"
                              type="number"
                              min={0}
                              max={100}
                              value={pct}
                              onChange={e => handlePctChange(step.tipo_maquina, m.id_ihm, e.target.value)}
                            />
                            <span className="fluxo-pct-label">%</span>
                          </div>
                        ) : (
                          <div className="fluxo-maquina-pct">100%</div>
                        )}
                        <div className="fluxo-maquina-qty">{qty.toLocaleString("pt-BR")} un</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}

        {/* Nó de saída */}
        <div className="fluxo-step-wrap">
          <div className="fluxo-arrow">→</div>
          <div className="fluxo-node fluxo-node--saida">
            <div className="fluxo-node-label">Saída</div>
            <div className="fluxo-node-qty">{op.quantidade.toLocaleString("pt-BR")} un</div>
          </div>
        </div>
      </div>

      {hasParallel && (
        <div className="fluxo-actions">
          <span className="fluxo-hint">Ajuste os percentuais nas etapas paralelas para distribuir a produção.</span>
          <button className="fluxo-save-btn" onClick={handleSave} disabled={saving}>
            {saving ? "Salvando..." : savedOk ? "Salvo!" : "Salvar Distribuição"}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Algoritmo de rastreamento de peças ──────────────────────────────────────
// Dado N peças e estágios em sequência, infere o status de cada peça em cada estágio.
// Peças são numeradas 1..N e processadas em ordem. Estágios com máquinas paralelas
// dividem o range de peças pelo percentual de cada máquina.
function computePieceGrid(pieces, steps) {
  if (!steps || steps.length === 0) return { stages: [], rows: [] };

  // Agrega estatísticas de etapa por tipo de máquina (mantém header funcionando)
  const stages = [...steps]
    .sort((a, b) => {
      const d = a.ordem - b.ordem;
      if (d !== 0) return d;
      return (a.maquinas[0]?.id_ihm ?? 0) - (b.maquinas[0]?.id_ihm ?? 0);
    })
    .map(step => ({
      ordem:   step.ordem,
      tipo:    step.tipo_maquina,
      maquinas: step.maquinas,
      total_aprovado:   step.maquinas.reduce((s, m) => s + (m.aprovado  || 0), 0),
      total_reprovado:  step.maquinas.reduce((s, m) => s + (m.reprovado || 0), 0),
      get total_processado() { return this.total_aprovado + this.total_reprovado; },
      any_produzindo:   step.maquinas.some(m => (m.status_maquina || "") === "produzindo"),
    }));

  if (!pieces || pieces.length === 0) return { stages, rows: [] };

  const n_etapas = stages.length;

  // Para cada etapa, verifica se alguma máquina está produzindo
  const produzindoPorEtapa = {};
  stages.forEach((st, i) => { produzindoPorEtapa[i + 1] = st.any_produzindo; });

  const rows = pieces.map(({ peca, etapa_atual, etapa_erro }) => {
    const cells = [];
    for (let stage_num = 1; stage_num <= n_etapas; stage_num++) {
      if (etapa_erro != null) {
        if (stage_num < etapa_erro)       cells.push("aprovado");
        else if (stage_num === etapa_erro) cells.push("reprovado");
        else                              cells.push("na");
      } else {
        if (stage_num < etapa_atual)      cells.push("aprovado");
        else if (stage_num === etapa_atual)
          cells.push(produzindoPorEtapa[stage_num] ? "produzindo" : "aguardando");
        else                              cells.push("aguardando");
      }
    }
    return { peca, cells };
  });

  return { stages, rows };
}

const PIECE_STATUS = {
  aprovado:  { bg: "#dcfce7", color: "#16a34a", icon: "✓", label: "Aprovado"  },
  reprovado: { bg: "#fee2e2", color: "#dc2626", icon: "✗", label: "Reprovado" },
  produzindo:{ bg: "#dbeafe", color: "#2563eb", icon: "⟳", label: "Produzindo"},
  aguardando:{ bg: "#f3f4f6", color: "#9ca3af", icon: "–", label: "Aguardando"},
  na:        { bg: "transparent", color: "#e5e7eb", icon: "·", label: "N/A"   },
};

function FluxogramaProducao({ op, fluxo }) {
  const { stages, rows } = computePieceGrid(fluxo.pieces || [], fluxo.steps || []);
  const MAX_VISIBLE = 80;
  // Garante ordem estável: peças sempre na mesma linha da tabela
  const sortedRows = [...rows].sort((a, b) => a.peca - b.peca);
  const visibleRows = sortedRows.slice(0, MAX_VISIBLE);
  const hidden = sortedRows.length - visibleRows.length;

  return (
    <div className="fpp-root">
      {/* Cabeçalho de estágios com sub-info por máquina */}
      <div className="fpp-stage-headers">
        {stages.map((st, si) => (
          <div key={si} className="fpp-stage-header">
            <div className="fpp-stage-tipo">{st.tipo}</div>
            {st.maquinas.map(m => (
              <div key={m.id_ihm} className="fpp-machine-info">
                <span className="fpp-mach-nome">{m.nome}</span>
                <span className="fpp-mach-stat fpp-mach-stat--ok">✓ {m.aprovado ?? 0}</span>
                <span className="fpp-mach-stat fpp-mach-stat--err">✗ {m.reprovado ?? 0}</span>
                <span className={`fpp-mach-badge fpp-mach-badge--${m.status_maquina ?? "parada"}`}>
                  {m.status_maquina ?? "parada"}
                </span>
              </div>
            ))}
            <div className="fpp-stage-totals">
              <span style={{ color: "#16a34a" }}>✓ {st.total_aprovado}</span>
              {" / "}
              <span style={{ color: "#dc2626" }}>✗ {st.total_reprovado}</span>
              {" / "}
              <span style={{ color: "#6b7280" }}>{st.total_processado} proc.</span>
            </div>
          </div>
        ))}
      </div>

      {/* Grade de peças */}
      <div className="fpp-grid-wrap">
        <table className="fpp-table">
          <thead>
            <tr>
              <th className="fpp-th fpp-th-num">#</th>
              {stages.map((st, si) => (
                <th key={si} className="fpp-th">{st.tipo}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map(row => (
              <tr key={row.peca}>
                <td className="fpp-td-num">{row.peca}</td>
                {row.cells.map((status, ci) => {
                  const s = PIECE_STATUS[status] || PIECE_STATUS.aguardando;
                  return (
                    <td key={ci} className="fpp-td" style={{ background: s.bg }}>
                      <span className="fpp-cell-icon" style={{ color: s.color }}>{s.icon}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
            {hidden > 0 && (
              <tr>
                <td className="fpp-td-hidden" colSpan={stages.length + 1}>
                  + {hidden} peças aguardando
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Legenda */}
      <div className="fpp-legend">
        {Object.entries(PIECE_STATUS).filter(([k]) => k !== "na").map(([key, val]) => (
          <span key={key} className="fpp-legend-item">
            <span style={{ color: val.color, fontWeight: 700 }}>{val.icon}</span> {val.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function MapaProducao({ ordens }) {
  const [expandedId, setExpandedId]     = useState(null);
  const [fluxos, setFluxos]             = useState({});
  const [loadingId, setLoadingId]       = useState(null);
  const [filtroStatus, setFiltroStatus] = useState("todos");
  const refreshTimerRef                 = useRef(null);

  const ordensFiltradas = ordens.filter(op => {
    if (filtroStatus === "ativos") {
      // Mantém visível mesmo que finalizada se estiver expandida no momento
      if (op.id === expandedId) return true;
      return op.status === "fila" || op.status === "em_producao";
    }
    return true;
  }).sort((a, b) => {
    const ordem = { em_producao: 0, fila: 1, finalizado: 2, cancelado: 3 };
    return (ordem[a.status] ?? 9) - (ordem[b.status] ?? 9);
  });

  // Auto-refresh quando uma OP em_producao está expandida
  useEffect(() => {
    if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    if (!expandedId) return;
    const op = ordens.find(o => o.id === expandedId);
    if (!op || op.status !== "em_producao") return;

    refreshTimerRef.current = setInterval(() => {
      fetch(`${API_BASE}/api/ordens/${expandedId}/fluxo`)
        .then(r => r.json())
        .then(data => setFluxos(prev => ({ ...prev, [expandedId]: data })))
        .catch(() => {});
    }, 2000);

    return () => clearInterval(refreshTimerRef.current);
  }, [expandedId, ordens]);

  async function toggleExpand(op) {
    if (expandedId === op.id) { setExpandedId(null); return; }
    setExpandedId(op.id);
    if (fluxos[op.id] && op.status !== "em_producao") return; // fila: usa cache
    setLoadingId(op.id);
    try {
      const res = await fetch(`${API_BASE}/api/ordens/${op.id}/fluxo`);
      const data = await res.json();
      setFluxos(prev => ({ ...prev, [op.id]: data }));
    } catch { /* silencia */ }
    finally { setLoadingId(null); }
  }

  function refreshFluxo(opId) {
    setFluxos(prev => { const n = { ...prev }; delete n[opId]; return n; });
    fetch(`${API_BASE}/api/ordens/${opId}/fluxo`)
      .then(r => r.json())
      .then(data => setFluxos(prev => ({ ...prev, [opId]: data })))
      .catch(() => {});
  }

  return (
    <div className="mapa-root">
      <div className="mapa-filtros">
        <button
          className={`mapa-filtro-btn${filtroStatus === "ativos" ? " active" : ""}`}
          onClick={() => setFiltroStatus("ativos")}
        >
          Ativos (Fila + Em Produção)
        </button>
        <button
          className={`mapa-filtro-btn${filtroStatus === "todos" ? " active" : ""}`}
          onClick={() => setFiltroStatus("todos")}
        >
          Todas as OPs
        </button>
      </div>

      {ordensFiltradas.length === 0 && (
        <div className="mapa-empty">Nenhuma OP para exibir.</div>
      )}

      {ordensFiltradas.map(op => {
        const isOpen    = expandedId === op.id;
        const isLoading = loadingId === op.id;
        const fluxo     = fluxos[op.id];
        const badge     = badgePrioridade(op.prioridade);
        const cor       = STATUS_CORES[op.status] ?? "#6b7280";
        const emProd    = op.status === "em_producao";

        return (
          <div key={op.id} className={`mapa-op-card${isOpen ? " mapa-op-card--open" : ""}`}>
            <div className="mapa-op-header" onClick={() => toggleExpand(op)}>
              <div className="mapa-op-header-left">
                <span className="mapa-op-status-dot" style={{ background: cor }} />
                <span className="mapa-op-numero">{op.numero_op}</span>
                <span className="mapa-op-linha">{op.linha_nome}</span>
                <span className="mapa-op-peca">{op.peca || "—"}</span>
              </div>
              <div className="mapa-op-header-right">
                <span className="mapa-op-qty">{op.quantidade.toLocaleString("pt-BR")} un</span>
                <span
                  className="mapa-op-status-badge"
                  style={{ background: cor + "22", color: cor, border: `1px solid ${cor}55` }}
                >
                  {STATUS_LABELS[op.status]}
                </span>
                {op.prioridade > 0 && (
                  <span className={`badge-prioridade ${badge.cls}`}>{badge.label}</span>
                )}
                {emProd && isOpen && (
                  <span className="mapa-op-live-badge">● ao vivo</span>
                )}
                <span className="mapa-op-expand-icon">{isOpen ? "▲" : "▼"}</span>
              </div>
            </div>

            {isOpen && (
              <div className="mapa-op-body">
                {isLoading && <div className="mapa-loading">Carregando fluxo...</div>}

                {!isLoading && fluxo && fluxo.steps?.length > 0 && (
                  (emProd || op.status === "finalizado")
                    ? <FluxogramaProducao op={op} fluxo={fluxo} />
                    : <FluxogramaOP op={op} fluxo={fluxo} onSave={() => refreshFluxo(op.id)} />
                )}

                {!isLoading && fluxo && fluxo.steps?.length > 0 &&
                  op.status === "finalizado" && (!fluxo.pieces || fluxo.pieces.length === 0) && (
                  <div className="mapa-sem-rota" style={{marginTop: 8}}>
                    Dados de rastreamento de peças não disponíveis para esta OP
                    (produzida antes do novo sistema de rastreamento).
                  </div>
                )}

                {!isLoading && fluxo && (!fluxo.steps || fluxo.steps.length === 0) && (
                  <div className="mapa-sem-rota">
                    Esta OP não tem roteiro configurado.
                    Configure em Configurações → Peças e Roteiros.
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---- Página principal ----
export default function OrdensProducao() {
  const [ordens, setOrdens]       = useState([]);
  const [linhas, setLinhas]       = useState([]);
  const [activeId, setActiveId]   = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [search, setSearch]       = useState("");
  const [filterLinha, setFilterLinha] = useState("");
  const [wsOk, setWsOk]           = useState(false);
  const [tab, setTab]             = useState("kanban");
  const wsRef = useRef(null);

  // WebSocket live updates
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_BASE}/api/ordens/ws`);
      wsRef.current = ws;
      ws.onopen    = () => setWsOk(true);
      ws.onmessage = (e) => {
        try { setOrdens(JSON.parse(e.data)); } catch {}
      };
      ws.onclose = () => {
        setWsOk(false);
        setTimeout(connect, 3000);
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, []);

  // Busca linhas para o filtro e modal
  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then((r) => r.json())
      .then(setLinhas)
      .catch(() => {});
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  function handleDragStart({ active }) {
    setActiveId(active.id);
  }

  function handleDragEnd({ active, over }) {
    setActiveId(null);
    if (!over) return;
    const novoStatus = over.id;
    const op = ordens.find((o) => o.id === active.id);
    if (!op || op.status === novoStatus) return;

    const statusAnterior = op.status;

    // Atualiza otimisticamente
    setOrdens((prev) =>
      prev.map((o) => (o.id === active.id ? { ...o, status: novoStatus } : o))
    );

    fetch(`${API_BASE}/api/ordens/${active.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: novoStatus }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          // Reverte atualização otimista
          setOrdens((prev) =>
            prev.map((o) => (o.id === active.id ? { ...o, status: statusAnterior } : o))
          );
          alert(err.detail || "Erro ao mover OP.");
        }
      })
      .catch(() => {
        // Reverte em caso de falha de rede
        setOrdens((prev) =>
          prev.map((o) => (o.id === active.id ? { ...o, status: statusAnterior } : o))
        );
      });
  }

  async function handleSaveOP(data) {
    const res = await fetch(`${API_BASE}/api/ordens`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      alert("Erro ao criar OP. Verifique a conexão com o servidor.");
      return;
    }
    setShowModal(false);
  }

  function handleDelete(id) {
    if (!window.confirm("Excluir esta ordem de produção?")) return;
    setOrdens((prev) => prev.filter((o) => o.id !== id));
    fetch(`${API_BASE}/api/ordens/${id}`, { method: "DELETE" }).catch(() => {});
  }

  // Filtragem
  const ordensFiltradas = ordens.filter((op) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      op.numero_op.toLowerCase().includes(q) ||
      op.peca.toLowerCase().includes(q) ||
      op.linha_nome.toLowerCase().includes(q);
    const matchLinha = !filterLinha || String(op.linha_id) === filterLinha;
    return matchSearch && matchLinha;
  });

  const activeOp = activeId ? ordens.find((o) => o.id === activeId) : null;

  const counts = {
    fila:        ordens.filter((o) => o.status === "fila").length,
    em_producao: ordens.filter((o) => o.status === "em_producao").length,
    finalizado:  ordens.filter((o) => o.status === "finalizado").length,
    cancelado:   ordens.filter((o) => o.status === "cancelado").length,
  };

  return (
    <div className="op-page">
      {/* Cabeçalho */}
      <div className="op-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h1 className="op-title">Ordens de Produção</h1>
          <span
            title={wsOk ? "Conectado — atualizando em tempo real" : "Reconectando..."}
            style={{
              width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
              background: wsOk ? "#16a34a" : "#d97706",
              boxShadow: wsOk ? "0 0 0 0 rgba(22,163,74,.4)" : "none",
              animation: wsOk ? "pulse-green 1.5s infinite" : "none",
            }}
          />
          {!wsOk && (
            <span style={{ fontSize: "0.75rem", color: "#d97706", fontWeight: 600 }}>
              Reconectando...
            </span>
          )}
        </div>
        <div className="op-header-actions">
          <input
            className="op-search"
            placeholder="Buscar OP, peça ou linha..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="op-filter-select"
            value={filterLinha}
            onChange={(e) => setFilterLinha(e.target.value)}
          >
            <option value="">Todas as linhas</option>
            {linhas.map((l) => (
              <option key={l.id} value={l.id}>{l.nome}</option>
            ))}
          </select>
          <button className="btn-nova-op" onClick={() => setShowModal(true)}>
            + Nova OP
          </button>
        </div>
      </div>


      {/* Estatísticas */}
      <div className="op-stats">
        <div className="op-stat">
          <span className="op-stat-label">Total</span>
          <span className="op-stat-value">{ordens.length}</span>
        </div>
        <div className="op-stat">
          <span className="op-stat-label">Na fila</span>
          <span className="op-stat-value blue">{counts.fila}</span>
        </div>
        <div className="op-stat">
          <span className="op-stat-label">Em produção</span>
          <span className="op-stat-value orange">{counts.em_producao}</span>
        </div>
        <div className="op-stat">
          <span className="op-stat-label">Finalizadas</span>
          <span className="op-stat-value green">{counts.finalizado}</span>
        </div>
        {counts.cancelado > 0 && (
          <div className="op-stat">
            <span className="op-stat-label">Canceladas</span>
            <span className="op-stat-value muted">{counts.cancelado}</span>
          </div>
        )}
      </div>

      {/* Abas */}
      <div className="op-tabs">
        <button
          className={`op-tab-btn${tab === "kanban" ? " op-tab-btn--active" : ""}`}
          onClick={() => setTab("kanban")}
        >
          Kanban
        </button>
        <button
          className={`op-tab-btn${tab === "mapa" ? " op-tab-btn--active" : ""}`}
          onClick={() => setTab("mapa")}
        >
          Mapa de Produção
        </button>
      </div>

      {/* Board Kanban */}
      {tab === "kanban" && (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="op-board">
            {COLUNAS.map((col) => (
              <Coluna
                key={col.id}
                coluna={col}
                ordens={ordensFiltradas.filter((o) => o.status === col.id)}
                onDelete={handleDelete}
              />
            ))}
          </div>

          <DragOverlay>
            {activeOp && (
              <OPCard op={activeOp} onDelete={() => {}} isOverlay />
            )}
          </DragOverlay>
        </DndContext>
      )}

      {/* Mapa de Produção */}
      {tab === "mapa" && (
        <MapaProducao ordens={ordensFiltradas} />
      )}

      {/* Modal */}
      {showModal && linhas.length > 0 && (
        <NovaOPModal
          linhas={linhas}
          onClose={() => setShowModal(false)}
          onSave={handleSaveOP}
        />
      )}
    </div>
  );
}
