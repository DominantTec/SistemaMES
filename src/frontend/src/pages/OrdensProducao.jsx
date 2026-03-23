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
    isDragging  ? "is-dragging" : "",
    isOverlay   ? "overlay"     : "",
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

      <div className="op-card-info">
        <div className="op-card-info-item">
          <span className="op-card-info-label">Quantidade</span>
          <span className="op-card-info-value">{op.quantidade.toLocaleString("pt-BR")} un</span>
        </div>
        <div className="op-card-info-item">
          <span className="op-card-info-label">Meta / hora</span>
          <span className="op-card-info-value">{op.meta_hora} pç/h</span>
        </div>
      </div>

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
    numero_op: "",
    linha_id: linhas[0]?.id ?? "",
    peca: "",
    quantidade: "",
    meta_hora: "",
    prioridade: "0",
    observacoes: "",
  });
  const [loading, setLoading] = useState(false);

  // Busca próximo número ao abrir
  useEffect(() => {
    fetch(`${API_BASE}/api/ordens/proximo-numero`)
      .then((r) => r.json())
      .then((d) => setForm((f) => ({ ...f, numero_op: d.numero })))
      .catch(() => {});
  }, []);

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSave() {
    if (!form.numero_op || !form.linha_id || !form.peca) return;
    setLoading(true);
    await onSave({
      numero_op:  form.numero_op,
      linha_id:   Number(form.linha_id),
      peca:       form.peca,
      quantidade: Number(form.quantidade) || 0,
      meta_hora:  Number(form.meta_hora)  || 0,
      prioridade: Number(form.prioridade) || 0,
      observacoes: form.observacoes,
    });
    setLoading(false);
  }

  const valid = form.numero_op && form.linha_id && form.peca;

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
            <input
              value={form.peca}
              onChange={(e) => set("peca", e.target.value)}
              placeholder="Ex: PRODUTO-A"
            />
          </div>

          <div className="op-modal-field">
            <label>Quantidade (un)</label>
            <input
              type="number"
              min="0"
              value={form.quantidade}
              onChange={(e) => set("quantidade", e.target.value)}
              placeholder="0"
            />
          </div>

          <div className="op-modal-field">
            <label>Meta por hora (pç/h)</label>
            <input
              type="number"
              min="0"
              value={form.meta_hora}
              onChange={(e) => set("meta_hora", e.target.value)}
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

// ---- Página principal ----
export default function OrdensProducao() {
  const [ordens, setOrdens]       = useState([]);
  const [linhas, setLinhas]       = useState([]);
  const [activeId, setActiveId]   = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [search, setSearch]       = useState("");
  const [filterLinha, setFilterLinha] = useState("");
  const [wsOk, setWsOk]           = useState(false);
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

    // Atualiza otimisticamente
    setOrdens((prev) =>
      prev.map((o) => (o.id === active.id ? { ...o, status: novoStatus } : o))
    );

    fetch(`${API_BASE}/api/ordens/${active.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: novoStatus }),
    }).catch(() => {});
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
      </div>

      {/* Board Kanban */}
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
