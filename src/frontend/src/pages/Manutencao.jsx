import { useEffect, useRef, useState, useCallback } from "react";
import "./Manutencao.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE    = import.meta.env.VITE_API_BASE || DEFAULT_API;
const WS_BASE     = API_BASE.replace(/^http/, "ws");

// ─── helpers ─────────────────────────────────────────────────────────────────
function fmtMin(min) {
  if (min == null) return "—";
  if (min < 60) return `${min}m`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

function fmtDt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function elapsed(iso) {
  if (!iso) return null;
  const diff = Math.floor((Date.now() - new Date(iso)) / 60000);
  return fmtMin(diff);
}

// ─── sub-components ───────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const labels = { aberta: "Aberta", em_andamento: "Em Andamento", concluida: "Concluída", cancelada: "Cancelada" };
  return <span className={`man-status-badge ${status}`}>{labels[status] ?? status}</span>;
}

function TipoBadge({ tipo }) {
  return <span className={`man-status-badge ${tipo}`}>{tipo === "manual" ? "Manual" : "Auto"}</span>;
}

// ─── Nova OS Modal ────────────────────────────────────────────────────────────
function NovaOSModal({ lines, onClose, onCreated }) {
  const [machines, setMachines] = useState([]);
  const [form, setForm] = useState({
    id_ihm: "", nome_ihm: "", id_linha: "", nome_linha: "",
    motivo_abertura: "Chamado manual", manutentor: "",
  });

  useEffect(() => {
    if (!form.id_linha) { setMachines([]); return; }
    fetch(`${API_BASE}/api/lines/${form.id_linha}/detail`)
      .then(r => r.json())
      .then(d => setMachines(Array.isArray(d) ? d : d.maquinas || []))
      .catch(() => {});
  }, [form.id_linha]);

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function handleMachine(id) {
    const m = machines.find(x => String(x.id) === String(id));
    set("id_ihm", id);
    set("nome_ihm", m ? (m.nome ?? "") : "");
  }

  function handleLine(id) {
    const l = lines.find(x => String(x.id) === String(id));
    set("id_linha", id);
    set("nome_linha", l ? (l.nome ?? "") : "");
    set("id_ihm", "");
    set("nome_ihm", "");
  }

  async function submit(e) {
    e.preventDefault();
    if (!form.id_ihm) return;
    const body = {
      id_ihm:          parseInt(form.id_ihm),
      nome_ihm:        form.nome_ihm,
      id_linha:        form.id_linha ? parseInt(form.id_linha) : null,
      nome_linha:      form.nome_linha,
      motivo_abertura: form.motivo_abertura || "Chamado manual",
      manutentor:      form.manutentor,
    };
    await fetch(`${API_BASE}/api/manutencao`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    onCreated();
    onClose();
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <h2 className="modal-title">Nova Ordem de Serviço</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="modal-grid-2">
            <div className="modal-field">
              <label>Linha</label>
              <select value={form.id_linha} onChange={e => handleLine(e.target.value)} required>
                <option value="">Selecione...</option>
                {lines.map(l => (
                  <option key={l.id} value={l.id}>{l.nome}</option>
                ))}
              </select>
            </div>
            <div className="modal-field">
              <label>Máquina</label>
              <select value={form.id_ihm} onChange={e => handleMachine(e.target.value)} required disabled={!form.id_linha}>
                <option value="">Selecione...</option>
                {machines.map(m => (
                  <option key={m.id} value={m.id}>{m.nome}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="modal-field">
            <label>Motivo / Descrição do chamado</label>
            <textarea
              rows={3}
              value={form.motivo_abertura}
              onChange={e => set("motivo_abertura", e.target.value)}
              placeholder="Descreva o problema observado..."
            />
          </div>

          <div className="modal-field">
            <label>Manutentor designado (opcional)</label>
            <input
              type="text"
              value={form.manutentor}
              onChange={e => set("manutentor", e.target.value)}
              placeholder="Nome do manutentor"
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="man-btn-sm gray" onClick={onClose}>Cancelar</button>
            <button type="submit" className="man-btn-primary">Abrir OS</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── OS Detail / Action Modal ─────────────────────────────────────────────────
function OSModal({ os, onClose, onAction }) {
  const [tab, setTab] = useState("detalhe"); // detalhe | iniciar | concluir | cancelar
  const [form, setForm] = useState({ manutentor: os.manutentor || "", problema: os.problema || "", solucao: "", motivo_cancel: "" });

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  async function doAction(endpoint, body) {
    await fetch(`${API_BASE}/api/manutencao/${os.id_os}/${endpoint}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    onAction();
    onClose();
  }

  const canIniciar  = os.status === "aberta";
  const canConcluir = os.status === "aberta" || os.status === "em_andamento";
  const canCancelar = os.status === "aberta" || os.status === "em_andamento";
  const isClosed    = os.status === "concluida" || os.status === "cancelada";

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <div>
            <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>OS #{os.id_os}</p>
            <h2 className="modal-title">{os.nome_ihm}</h2>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* Status / tipo badges */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <StatusBadge status={os.status} />
          <TipoBadge tipo={os.tipo} />
          {os.nome_linha && <span style={{ fontSize: 13, color: "var(--muted)" }}>{os.nome_linha}</span>}
        </div>

        {/* Tempos */}
        <div className="modal-times">
          <div className="modal-time-block">
            <div className="modal-time-label">Espera</div>
            <div className="modal-time-value">{fmtMin(os.tempo_espera_min)}</div>
          </div>
          <div className="modal-time-block">
            <div className="modal-time-label">Reparo</div>
            <div className="modal-time-value">{fmtMin(os.tempo_reparo_min)}</div>
          </div>
          <div className="modal-time-block">
            <div className="modal-time-label">Total</div>
            <div className="modal-time-value">{fmtMin(os.tempo_total_min)}</div>
          </div>
        </div>

        {/* Info fields */}
        <div className="modal-grid-2">
          <div className="modal-field">
            <label>Abertura</label>
            <p>{fmtDt(os.dt_abertura)}</p>
          </div>
          {os.dt_inicio_atendimento && (
            <div className="modal-field">
              <label>Início atendimento</label>
              <p>{fmtDt(os.dt_inicio_atendimento)}</p>
            </div>
          )}
          {os.dt_conclusao && (
            <div className="modal-field">
              <label>Conclusão</label>
              <p>{fmtDt(os.dt_conclusao)}</p>
            </div>
          )}
        </div>

        {os.motivo_abertura && (
          <div className="modal-field">
            <label>Motivo de abertura</label>
            <p>{os.motivo_abertura}</p>
          </div>
        )}
        {os.manutentor && (
          <div className="modal-field">
            <label>Manutentor</label>
            <p>{os.manutentor}</p>
          </div>
        )}
        {os.problema && (
          <div className="modal-field">
            <label>Problema identificado</label>
            <p>{os.problema}</p>
          </div>
        )}
        {os.solucao && (
          <div className="modal-field">
            <label>Solução aplicada</label>
            <p>{os.solucao}</p>
          </div>
        )}
        {os.cancelamento && (
          <div className="modal-field">
            <label>Motivo cancelamento</label>
            <p>{os.cancelamento}</p>
          </div>
        )}

        {/* Action tabs */}
        {!isClosed && (
          <>
            <div style={{ borderTop: "1px solid var(--line, #e5e7eb)", paddingTop: 12 }}>
              <div className="man-tabs" style={{ display: "inline-flex" }}>
                {canIniciar  && <button className={`man-tab${tab === "iniciar"  ? " active" : ""}`} onClick={() => setTab("iniciar")}>Iniciar</button>}
                {canConcluir && <button className={`man-tab${tab === "concluir" ? " active" : ""}`} onClick={() => setTab("concluir")}>Concluir</button>}
                {canCancelar && <button className={`man-tab${tab === "cancelar" ? " active" : ""}`} onClick={() => setTab("cancelar")}>Cancelar</button>}
              </div>
            </div>

            {tab === "iniciar" && canIniciar && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="modal-field">
                  <label>Manutentor</label>
                  <input type="text" value={form.manutentor} onChange={e => set("manutentor", e.target.value)} placeholder="Nome do manutentor" />
                </div>
                <div className="modal-actions">
                  <button className="man-btn-sm amber" onClick={() => doAction("iniciar", { manutentor: form.manutentor })}>
                    Confirmar Início
                  </button>
                </div>
              </div>
            )}

            {tab === "concluir" && canConcluir && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="modal-field">
                  <label>Manutentor</label>
                  <input type="text" value={form.manutentor} onChange={e => set("manutentor", e.target.value)} placeholder="Nome do manutentor" />
                </div>
                <div className="modal-field">
                  <label>Problema identificado</label>
                  <textarea rows={2} value={form.problema} onChange={e => set("problema", e.target.value)} placeholder="Descreva o problema encontrado..." />
                </div>
                <div className="modal-field">
                  <label>Solução aplicada</label>
                  <textarea rows={2} value={form.solucao} onChange={e => set("solucao", e.target.value)} placeholder="Descreva o que foi feito para resolver..." />
                </div>
                <div className="modal-actions">
                  <button className="man-btn-sm green" onClick={() => doAction("concluir", { problema: form.problema, solucao: form.solucao, manutentor: form.manutentor })}>
                    Confirmar Conclusão
                  </button>
                </div>
              </div>
            )}

            {tab === "cancelar" && canCancelar && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="modal-field">
                  <label>Motivo do cancelamento</label>
                  <textarea rows={2} value={form.motivo_cancel} onChange={e => set("motivo_cancel", e.target.value)} placeholder="Por que está cancelando esta OS?" />
                </div>
                <div className="modal-actions">
                  <button className="man-btn-sm gray" onClick={() => doAction("cancelar", { motivo: form.motivo_cancel })}>
                    Confirmar Cancelamento
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        <div className="modal-actions">
          <button className="man-btn-sm gray" onClick={onClose}>Fechar</button>
        </div>
      </div>
    </div>
  );
}

// ─── Active OS Card ───────────────────────────────────────────────────────────
function OSCard({ os, onOpen }) {
  return (
    <div className={`man-os-card status-${os.status}`}>
      <div className="man-os-card-header">
        <div>
          <div className="man-os-id">OS #{os.id_os} · {os.nome_linha}</div>
          <div className="man-os-machine">{os.nome_ihm}</div>
        </div>
        <StatusBadge status={os.status} />
      </div>

      {os.motivo_abertura && (
        <div className="man-os-motivo">{os.motivo_abertura}</div>
      )}

      <div className="man-os-times">
        <span>Aberta: {fmtDt(os.dt_abertura)} ({elapsed(os.dt_abertura)} atrás)</span>
        {os.manutentor && <span>Manutentor: {os.manutentor}</span>}
      </div>

      <div className="man-os-card-actions">
        <TipoBadge tipo={os.tipo} />
        <button className="man-btn-sm detail" onClick={() => onOpen(os)}>Ver / Agir</button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
const STATUS_TABS = [
  { key: "",             label: "Todas" },
  { key: "aberta",       label: "Abertas" },
  { key: "em_andamento", label: "Em Andamento" },
  { key: "concluida",    label: "Concluídas" },
  { key: "cancelada",    label: "Canceladas" },
];

export default function Manutencao() {
  const [osList,    setOsList]    = useState([]);
  const [stats,     setStats]     = useState({});
  const [lines,     setLines]     = useState([]);
  const [wsStatus,  setWsStatus]  = useState("disconnected");
  const [tabStatus, setTabStatus] = useState("");
  const [filterLine, setFilterLine] = useState("");
  const [search,    setSearch]    = useState("");
  const [selectedOS, setSelectedOS] = useState(null);
  const [showNova,  setShowNova]  = useState(false);
  const wsRef = useRef(null);

  // Fetch lines for filter / nova OS
  useEffect(() => {
    fetch(`${API_BASE}/api/lines`)
      .then(r => r.json())
      .then(setLines)
      .catch(() => {});
  }, []);

  // WebSocket
  const connect = useCallback(() => {
    if (wsRef.current) { try { wsRef.current.close(); } catch (_) {} }
    const ws = new WebSocket(`${WS_BASE}/api/manutencao/ws`);
    wsRef.current = ws;

    ws.onopen  = () => setWsStatus("connected");
    ws.onclose = () => { setWsStatus("disconnected"); setTimeout(connect, 4000); };
    ws.onerror = () => ws.close();
    ws.onmessage = e => {
      try {
        const d = JSON.parse(e.data);
        if (d.os_list) setOsList(d.os_list);
        if (d.stats)   setStats(d.stats);
      } catch (_) {}
    };
  }, []);

  useEffect(() => {
    connect();
    return () => { try { wsRef.current?.close(); } catch (_) {} };
  }, [connect]);

  // Reload after action (WS will pick it up, but also force-refresh stats)
  function reload() {
    fetch(`${API_BASE}/api/manutencao/stats`).then(r => r.json()).then(setStats).catch(() => {});
    fetch(`${API_BASE}/api/manutencao`).then(r => r.json()).then(setOsList).catch(() => {});
  }

  // Derived lists
  const activeOS = osList.filter(o => o.status === "aberta" || o.status === "em_andamento");

  const filtered = osList.filter(o => {
    if (tabStatus && o.status !== tabStatus) return false;
    if (filterLine && String(o.id_linha) !== filterLine) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        o.nome_ihm.toLowerCase().includes(q) ||
        o.nome_linha.toLowerCase().includes(q) ||
        o.motivo_abertura.toLowerCase().includes(q) ||
        o.manutentor.toLowerCase().includes(q) ||
        String(o.id_os).includes(q)
      );
    }
    return true;
  });

  const showActive = !tabStatus || tabStatus === "aberta" || tabStatus === "em_andamento";

  return (
    <div className="man-root">
      {/* ── Topbar ── */}
      <div className="man-topbar">
        <h1>🔧 Manutenção / Ordens de Serviço</h1>
        <div className="man-topbar-right">
          <span className={`ws-dot ${wsStatus}`} title={wsStatus} />
          <button className="man-btn-primary" onClick={() => setShowNova(true)}>+ Nova OS</button>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="man-stats-row">
        <div className="man-stat-card red">
          <span className="man-stat-label">Em Aberto</span>
          <span className="man-stat-value">{stats.abertas ?? 0}</span>
          <span className="man-stat-sub">{stats.em_andamento ?? 0} em andamento</span>
        </div>
        <div className="man-stat-card amber">
          <span className="man-stat-label">Hoje</span>
          <span className="man-stat-value">{stats.hoje ?? 0}</span>
          <span className="man-stat-sub">OS abertas hoje</span>
        </div>
        <div className="man-stat-card blue">
          <span className="man-stat-label">Semana</span>
          <span className="man-stat-value">{stats.semana ?? 0}</span>
          <span className="man-stat-sub">últimos 7 dias</span>
        </div>
        <div className="man-stat-card gray">
          <span className="man-stat-label">Mês</span>
          <span className="man-stat-value">{stats.mes ?? 0}</span>
          <span className="man-stat-sub">últimos 30 dias</span>
        </div>
        <div className="man-stat-card green">
          <span className="man-stat-label">MTTR (reparo)</span>
          <span className="man-stat-value">{fmtMin(Math.round(stats.mttr_reparo ?? 0))}</span>
          <span className="man-stat-sub">média 30 dias</span>
        </div>
        <div className="man-stat-card blue">
          <span className="man-stat-label">Espera média</span>
          <span className="man-stat-value">{fmtMin(Math.round(stats.tempo_espera_medio ?? 0))}</span>
          <span className="man-stat-sub">até manutentor chegar</span>
        </div>
      </div>

      {/* ── Active section ── */}
      {showActive && activeOS.length > 0 && (
        <div className="man-active-section">
          <p className="man-section-title">Em Andamento / Aguardando ({activeOS.length})</p>
          <div className="man-active-grid">
            {activeOS.map(o => (
              <OSCard key={o.id_os} os={o} onOpen={setSelectedOS} />
            ))}
          </div>
        </div>
      )}

      {/* ── History ── */}
      <div>
        <p className="man-section-title">Histórico de OS</p>

        {/* Filter bar */}
        <div className="man-filter-bar">
          <div className="man-tabs">
            {STATUS_TABS.map(t => (
              <button
                key={t.key}
                className={`man-tab${tabStatus === t.key ? " active" : ""}`}
                onClick={() => setTabStatus(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <select value={filterLine} onChange={e => setFilterLine(e.target.value)}>
            <option value="">Todas as linhas</option>
            {lines.map(l => (
              <option key={l.id} value={String(l.id)}>{l.nome}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Buscar máquina, manutentor..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ minWidth: 220 }}
          />
        </div>

        {/* List */}
        {filtered.length === 0 ? (
          <div className="man-empty">Nenhuma OS encontrada para os filtros selecionados.</div>
        ) : (
          <div className="man-list">
            {filtered.map(o => (
              <div key={o.id_os} className="man-list-item" onClick={() => setSelectedOS(o)}>
                <div style={{ width: 4, height: 40, borderRadius: 2, flexShrink: 0, background: {
                  aberta: "#ef4444", em_andamento: "#f59e0b",
                  concluida: "#22c55e", cancelada: "#9ca3af",
                }[o.status] ?? "#e5e7eb" }} />
                <div className="man-list-left">
                  <span className="man-list-machine">{o.nome_ihm}</span>
                  <span className="man-list-meta">
                    {o.nome_linha}{o.manutentor ? ` · ${o.manutentor}` : ""}
                    {o.motivo_abertura ? ` · ${o.motivo_abertura.slice(0, 60)}` : ""}
                  </span>
                </div>
                <div className="man-list-right">
                  <StatusBadge status={o.status} />
                  <span className="man-list-time">
                    {o.tempo_total_min != null ? fmtMin(o.tempo_total_min) : elapsed(o.dt_abertura)}
                  </span>
                  <span className="man-list-time">OS #{o.id_os}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Modals ── */}
      {showNova && (
        <NovaOSModal
          lines={lines}
          onClose={() => setShowNova(false)}
          onCreated={reload}
        />
      )}
      {selectedOS && (
        <OSModal
          os={selectedOS}
          onClose={() => setSelectedOS(null)}
          onAction={reload}
        />
      )}
    </div>
  );
}
