import { useEffect, useRef, useState, useCallback } from "react";
import "./Alertas.css";

const DEFAULT_API  = `http://${window.location.hostname}:8000`;
const API_BASE     = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE      = API_BASE.replace(/^http/, "ws");

const TIPO_LABELS = {
  maquina_parada:        "Máquina parada",
  manutencao_prolongada: "Manutenção prolongada",
  oee_baixo:             "OEE baixo",
  refugo_alto:           "Refugo alto",
  op_atrasada:           "OP atrasada",
};

const TIPO_UNIDADE = {
  maquina_parada:        "min",
  manutencao_prolongada: "min",
  oee_baixo:             "%",
  refugo_alto:           "%",
  op_atrasada:           "%",
};

function tempoRelativo(iso) {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)   return `há ${Math.round(diff)}s`;
  if (diff < 3600) return `há ${Math.round(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.round(diff / 3600)}h`;
  return `há ${Math.round(diff / 86400)}d`;
}

function horaFormatada(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function SevBadge({ sev }) {
  return (
    <span className={`alerta-sev-badge sev-${sev}`}>
      {sev === "critico" ? "CRÍTICO" : sev === "aviso" ? "AVISO" : "INFO"}
    </span>
  );
}

function StatusBadge({ status }) {
  return (
    <span className={`alerta-status-badge ast-${status}`}>
      {status === "ativo" ? "Ativo" : status === "reconhecido" ? "Reconhecido" : "Resolvido"}
    </span>
  );
}

function TipoIcon({ tipo }) {
  const icons = {
    maquina_parada:        "⏸",
    manutencao_prolongada: "🔧",
    oee_baixo:             "📉",
    refugo_alto:           "⚠",
    op_atrasada:           "🕐",
  };
  return <span className="alerta-tipo-icon">{icons[tipo] ?? "🔔"}</span>;
}

// ── Card de um alerta ──────────────────────────────────────────────────────────
function AlertaCard({ alerta, onReconhecer, onResolver }) {
  const [expandido,    setExpandido]    = useState(false);
  const [reconhNome,   setReconhNome]   = useState("");
  const [resolucaoTxt, setResolucaoTxt] = useState("");
  const [showReconhForm, setShowReconhForm] = useState(false);
  const [showResolForm,  setShowResolForm]  = useState(false);

  const ehAtivo       = alerta.status === "ativo";
  const ehReconh      = alerta.status === "reconhecido";
  const ehResolvido   = alerta.status === "resolvido";

  return (
    <div className={`alerta-card sev-border-${alerta.severidade} ${ehResolvido ? "alerta-card-resolvido" : ""}`}>
      <div className="alerta-card-header" onClick={() => setExpandido(e => !e)}>
        <div className="alerta-card-left">
          <TipoIcon tipo={alerta.tipo} />
          <div className="alerta-card-info">
            <div className="alerta-card-titulo">
              <SevBadge sev={alerta.severidade} />
              <span>{alerta.titulo}</span>
            </div>
            <div className="alerta-card-meta">
              {alerta.nome_linha   && <span className="alerta-tag">📍 {alerta.nome_linha}</span>}
              {alerta.nome_maquina && <span className="alerta-tag">⚙ {alerta.nome_maquina}</span>}
              {alerta.numero_op    && <span className="alerta-tag">📋 OP {alerta.numero_op}</span>}
              {alerta.nu_valor !== null && alerta.nu_valor !== undefined && (
                <span className="alerta-tag">
                  {alerta.nu_valor.toFixed(1)}{TIPO_UNIDADE[alerta.tipo] ?? ""}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="alerta-card-right">
          <StatusBadge status={alerta.status} />
          <span className="alerta-hora">{horaFormatada(alerta.dt_criacao)}</span>
          <span className="alerta-expand-icon">{expandido ? "▲" : "▼"}</span>
        </div>
      </div>

      {expandido && (
        <div className="alerta-card-body">
          <p className="alerta-descricao">{alerta.descricao}</p>

          {alerta.reconhecido_por && (
            <p className="alerta-reconhinfo">
              ✓ Reconhecido por <strong>{alerta.reconhecido_por}</strong> {tempoRelativo(alerta.dt_reconhecido)}
            </p>
          )}
          {alerta.resolucao && (
            <p className="alerta-resolucao-info">
              ✓ Resolução: {alerta.resolucao}
            </p>
          )}

          {!ehResolvido && (
            <div className="alerta-acoes">
              {ehAtivo && !showReconhForm && (
                <button className="btn-reconhecer" onClick={() => setShowReconhForm(true)}>
                  Reconhecer
                </button>
              )}
              {ehAtivo && showReconhForm && (
                <div className="alerta-inline-form">
                  <input
                    className="alerta-input"
                    placeholder="Seu nome (opcional)"
                    value={reconhNome}
                    onChange={e => setReconhNome(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && onReconhecer(alerta.id, reconhNome || "Operador")}
                    autoFocus
                  />
                  <button className="btn-confirmar"
                    onClick={() => { onReconhecer(alerta.id, reconhNome || "Operador"); setShowReconhForm(false); }}>
                    Confirmar
                  </button>
                  <button className="btn-cancelar" onClick={() => setShowReconhForm(false)}>Cancelar</button>
                </div>
              )}

              {!showResolForm && (
                <button className="btn-resolver" onClick={() => setShowResolForm(true)}>
                  Resolver
                </button>
              )}
              {showResolForm && (
                <div className="alerta-inline-form">
                  <input
                    className="alerta-input"
                    placeholder="Descreva a solução (opcional)"
                    value={resolucaoTxt}
                    onChange={e => setResolucaoTxt(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && onResolver(alerta.id, resolucaoTxt)}
                    autoFocus
                  />
                  <button className="btn-confirmar"
                    onClick={() => { onResolver(alerta.id, resolucaoTxt); setShowResolForm(false); }}>
                    Confirmar
                  </button>
                  <button className="btn-cancelar" onClick={() => setShowResolForm(false)}>Cancelar</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Modal de configuração de regras ───────────────────────────────────────────
function ConfigModal({ onClose, linhas }) {
  const [configs,  setConfigs]  = useState([]);
  const [editando, setEditando] = useState(null); // null | objeto de config
  const [salvando, setSalvando] = useState(false);
  const [msg,      setMsg]      = useState("");

  const carregarConfigs = useCallback(() => {
    fetch(`${API_BASE}/api/alertas/config`)
      .then(r => r.json())
      .then(setConfigs)
      .catch(() => {});
  }, []);

  useEffect(() => { carregarConfigs(); }, [carregarConfigs]);

  async function salvar() {
    setSalvando(true);
    try {
      const method = editando.id ? "PUT" : "POST";
      const url    = editando.id
        ? `${API_BASE}/api/alertas/config/${editando.id}`
        : `${API_BASE}/api/alertas/config`;
      await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editando),
      });
      setEditando(null);
      carregarConfigs();
      setMsg("Regra salva.");
    } catch {
      setMsg("Erro ao salvar.");
    }
    setSalvando(false);
  }

  async function excluir(id) {
    if (!window.confirm("Excluir esta regra?")) return;
    await fetch(`${API_BASE}/api/alertas/config/${id}`, { method: "DELETE" });
    carregarConfigs();
  }

  async function toggleAtivo(cfg) {
    await fetch(`${API_BASE}/api/alertas/config/${cfg.id}/toggle?ativo=${!cfg.ativo}`, { method: "PATCH" });
    carregarConfigs();
  }

  const novaRegra = {
    tipo: "maquina_parada", nome: "", descricao: "",
    limiar: 15, severidade: "aviso", id_linha: null, ativo: true,
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <h2 className="modal-title">Configuração de Regras de Alerta</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {msg && <div className="modal-msg">{msg}</div>}

        {!editando ? (
          <>
            <div className="modal-toolbar">
              <button className="btn-nova-regra" onClick={() => setEditando({ ...novaRegra })}>
                + Nova Regra
              </button>
            </div>
            <div className="config-lista">
              {configs.length === 0 && (
                <div className="config-empty">Nenhuma regra configurada.</div>
              )}
              {configs.map(cfg => (
                <div key={cfg.id} className={`config-item ${cfg.ativo ? "" : "config-item-off"}`}>
                  <div className="config-item-left">
                    <span className={`cfg-sev-dot dot-${cfg.severidade}`} />
                    <div>
                      <div className="config-item-nome">{cfg.nome}</div>
                      <div className="config-item-sub">
                        {TIPO_LABELS[cfg.tipo] ?? cfg.tipo} · limiar: {cfg.limiar}{TIPO_UNIDADE[cfg.tipo] ?? ""}
                        {cfg.nome_linha ? ` · ${cfg.nome_linha}` : " · Todas as linhas"}
                      </div>
                    </div>
                  </div>
                  <div className="config-item-acoes">
                    <label className="toggle-switch">
                      <input type="checkbox" checked={cfg.ativo} onChange={() => toggleAtivo(cfg)} />
                      <span className="toggle-slider" />
                    </label>
                    <button className="btn-editar-cfg" onClick={() => setEditando({ ...cfg })}>Editar</button>
                    <button className="btn-excluir-cfg" onClick={() => excluir(cfg.id)}>✕</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="config-form">
            <h3 className="config-form-title">{editando.id ? "Editar Regra" : "Nova Regra"}</h3>

            <label className="form-label">Tipo de alerta</label>
            <select className="form-select"
              value={editando.tipo}
              onChange={e => setEditando(p => ({ ...p, tipo: e.target.value }))}>
              {Object.entries(TIPO_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>

            <label className="form-label">Nome da regra</label>
            <input className="form-input" value={editando.nome}
              onChange={e => setEditando(p => ({ ...p, nome: e.target.value }))}
              placeholder="Ex: Máquina parada crítica" />

            <div className="form-row">
              <div className="form-col">
                <label className="form-label">
                  Limiar ({TIPO_UNIDADE[editando.tipo] ?? "valor"})
                </label>
                <input className="form-input" type="number" min="0" value={editando.limiar}
                  onChange={e => setEditando(p => ({ ...p, limiar: parseFloat(e.target.value) || 0 }))} />
              </div>
              <div className="form-col">
                <label className="form-label">Severidade</label>
                <select className="form-select" value={editando.severidade}
                  onChange={e => setEditando(p => ({ ...p, severidade: e.target.value }))}>
                  <option value="critico">Crítico</option>
                  <option value="aviso">Aviso</option>
                  <option value="info">Info</option>
                </select>
              </div>
            </div>

            <label className="form-label">Linha de produção (deixe em branco para todas)</label>
            <select className="form-select"
              value={editando.id_linha ?? ""}
              onChange={e => setEditando(p => ({
                ...p, id_linha: e.target.value ? parseInt(e.target.value) : null,
              }))}>
              <option value="">Todas as linhas</option>
              {linhas.map(l => (
                <option key={l.id} value={l.id}>{l.nome}</option>
              ))}
            </select>

            <label className="form-label">Descrição (opcional)</label>
            <textarea className="form-textarea" rows={2} value={editando.descricao ?? ""}
              onChange={e => setEditando(p => ({ ...p, descricao: e.target.value }))}
              placeholder="Descreva quando este alerta deve disparar..." />

            <div className="config-form-footer">
              <button className="btn-cancelar-form" onClick={() => setEditando(null)}>Cancelar</button>
              <button className="btn-salvar-form" onClick={salvar} disabled={salvando || !editando.nome}>
                {salvando ? "Salvando…" : "Salvar Regra"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Página principal ───────────────────────────────────────────────────────────
export default function Alertas() {
  const [alertas,   setAlertas]   = useState([]);
  const [stats,     setStats]     = useState({});
  const [linhas,    setLinhas]    = useState([]);
  const [wsStatus,  setWsStatus]  = useState("connecting");
  const [showModal, setShowModal] = useState(false);

  // Filtros
  const [filtroStatus,   setFiltroStatus]   = useState("ativos");   // ativos | reconhecido | resolvido | todos
  const [filtroSev,      setFiltroSev]      = useState("todos");
  const [filtroLinha,    setFiltroLinha]    = useState("");
  const [busca,          setBusca]          = useState("");

  const wsRef = useRef(null);

  // WebSocket
  useEffect(() => {
    function conectar() {
      const ws = new WebSocket(`${WS_BASE}/api/alertas/ws`);
      wsRef.current = ws;

      ws.onopen  = () => setWsStatus("ok");
      ws.onclose = () => { setWsStatus("off"); setTimeout(conectar, 4000); };
      ws.onerror = () => ws.close();
      ws.onmessage = e => {
        try {
          const d = JSON.parse(e.data);
          if (d.alertas) setAlertas(d.alertas);
          if (d.stats)   setStats(d.stats);
        } catch {}
      };
    }
    conectar();
    return () => wsRef.current?.close();
  }, []);

  // Linhas para filtro e modal
  useEffect(() => {
    fetch(`${API_BASE}/api/lines`)
      .then(r => r.json())
      .then(data => setLinhas(data.map(l => ({ id: l.id, nome: l.nome }))))
      .catch(() => {});
  }, []);

  // Ações
  async function reconhecer(id, nome) {
    await fetch(`${API_BASE}/api/alertas/${id}/reconhecer`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reconhecido_por: nome }),
    });
  }

  async function resolver(id, txt) {
    await fetch(`${API_BASE}/api/alertas/${id}/resolver`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolucao: txt || null }),
    });
  }

  // Filtros aplicados
  const alertasFiltrados = alertas.filter(a => {
    if (filtroStatus === "ativos"      && !["ativo", "reconhecido"].includes(a.status)) return false;
    if (filtroStatus === "reconhecido" && a.status !== "reconhecido") return false;
    if (filtroStatus === "resolvido"   && a.status !== "resolvido")   return false;
    if (filtroSev !== "todos"          && a.severidade !== filtroSev) return false;
    if (filtroLinha && String(a.id_linha) !== filtroLinha)            return false;
    if (busca) {
      const q = busca.toLowerCase();
      if (!a.titulo?.toLowerCase().includes(q) &&
          !a.descricao?.toLowerCase().includes(q) &&
          !a.nome_maquina?.toLowerCase().includes(q) &&
          !a.nome_linha?.toLowerCase().includes(q) &&
          !a.numero_op?.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const nAtivos = stats.nao_reconhecidos ?? 0;

  return (
    <div className="alerta-root">
      {/* ── Cabeçalho ── */}
      <div className="alerta-topbar">
        <div>
          <h1 className="alerta-page-title">
            Alertas e Notificações
            {nAtivos > 0 && <span className="alerta-page-badge">{nAtivos}</span>}
          </h1>
          <p className="alerta-page-sub">
            Monitoramento automático de condições críticas na produção
          </p>
        </div>
        <div className="alerta-topbar-right">
          <div className={`ws-dot ws-${wsStatus}`} title={wsStatus === "ok" ? "Conectado" : "Reconectando…"} />
          <button className="btn-config-alertas" onClick={() => setShowModal(true)}>
            ⚙ Configurar Regras
          </button>
        </div>
      </div>

      {/* ── Estatísticas ── */}
      <div className="alerta-stats-row">
        <div className="alerta-stat-card stat-critico">
          <div className="alerta-stat-val">{stats.criticos ?? 0}</div>
          <div className="alerta-stat-lbl">Críticos ativos</div>
        </div>
        <div className="alerta-stat-card stat-ativo">
          <div className="alerta-stat-val">{stats.total_ativos ?? 0}</div>
          <div className="alerta-stat-lbl">Total ativos</div>
        </div>
        <div className="alerta-stat-card stat-reconhecido">
          <div className="alerta-stat-val">{stats.reconhecidos ?? 0}</div>
          <div className="alerta-stat-lbl">Reconhecidos</div>
        </div>
        <div className="alerta-stat-card stat-hoje">
          <div className="alerta-stat-val">{stats.hoje ?? 0}</div>
          <div className="alerta-stat-lbl">Hoje</div>
        </div>
        <div className="alerta-stat-card stat-semana">
          <div className="alerta-stat-val">{stats.semana ?? 0}</div>
          <div className="alerta-stat-lbl">Últimos 7 dias</div>
        </div>
      </div>

      {/* ── Filtros ── */}
      <div className="alerta-filtros">
        <div className="alerta-filtros-left">
          <div className="alerta-tab-group">
            {[
              { key: "ativos",      label: "Ativos", count: stats.total_ativos },
              { key: "reconhecido", label: "Reconhecidos", count: stats.reconhecidos },
              { key: "resolvido",   label: "Resolvidos", count: null },
              { key: "todos",       label: "Todos", count: null },
            ].map(t => (
              <button key={t.key}
                className={`alerta-tab ${filtroStatus === t.key ? "active" : ""}`}
                onClick={() => setFiltroStatus(t.key)}>
                {t.label}
                {t.count !== null && t.count > 0 && (
                  <span className="tab-count">{t.count}</span>
                )}
              </button>
            ))}
          </div>

          <select className="alerta-select" value={filtroSev}
            onChange={e => setFiltroSev(e.target.value)}>
            <option value="todos">Todas severidades</option>
            <option value="critico">Crítico</option>
            <option value="aviso">Aviso</option>
            <option value="info">Info</option>
          </select>

          <select className="alerta-select" value={filtroLinha}
            onChange={e => setFiltroLinha(e.target.value)}>
            <option value="">Todas as linhas</option>
            {linhas.map(l => (
              <option key={l.id} value={String(l.id)}>{l.nome}</option>
            ))}
          </select>
        </div>

        <div className="alerta-filtros-right">
          <input className="alerta-busca" placeholder="Buscar…"
            value={busca} onChange={e => setBusca(e.target.value)} />
        </div>
      </div>

      {/* ── Lista de alertas ── */}
      <div className="alerta-lista">
        {alertasFiltrados.length === 0 ? (
          <div className="alerta-vazio">
            {filtroStatus === "ativos"
              ? "✅ Nenhum alerta ativo no momento."
              : "Nenhum alerta encontrado para os filtros selecionados."}
          </div>
        ) : (
          alertasFiltrados.map(a => (
            <AlertaCard
              key={a.id}
              alerta={a}
              onReconhecer={reconhecer}
              onResolver={resolver}
            />
          ))
        )}
      </div>

      {showModal && (
        <ConfigModal onClose={() => setShowModal(false)} linhas={linhas} />
      )}
    </div>
  );
}
