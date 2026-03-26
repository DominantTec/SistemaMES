import { useEffect, useState } from "react";
import "./Configuracoes.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

const STATUS_STYLE = {
  "Em Produção":    { color: "#16a34a", bg: "#dcfce7" },
  "Parada":         { color: "#dc2626", bg: "#fee2e2" },
  "Em Manutenção":  { color: "#7c3aed", bg: "#ede9fe" },
  "Limpeza":        { color: "#2563eb", bg: "#dbeafe" },
  "Ag. Manutentor": { color: "#d97706", bg: "#fef3c7" },
};

const DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
const DIAS_SHORT  = { "Segunda": "Seg", "Terça": "Ter", "Quarta": "Qua", "Quinta": "Qui", "Sexta": "Sex", "Sábado": "Sáb", "Domingo": "Dom" };
const TODAY_NAME  = DIAS_SEMANA[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1];

function statusStyle(s) {
  return STATUS_STYLE[s] || { color: "#6b7280", bg: "#f3f4f6" };
}

function novoTurno() {
  return { dia: "Segunda", nome: "", inicio: "07:00", fim: "15:00", ativo: true };
}

/* ── Seção: Gestão de Turnos (por linha) ─────────────────── */
function GestaoTurnos() {
  const [linhas, setLinhas]         = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [turnos, setTurnos]         = useState([]);
  const [saving, setSaving]         = useState(false);
  const [savedMsg, setSavedMsg]     = useState("");
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then((r) => r.json())
      .then((data) => { setLinhas(data); if (data.length > 0) setSelectedId(data[0].id); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`)
      .then((r) => r.json())
      .then((data) => setTurnos(data.turnos ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedId]);

  function setField(index, field, value) {
    setTurnos((prev) => prev.map((t, i) => (i === index ? { ...t, [field]: value } : t)));
  }

  function addTurno() {
    setTurnos((prev) => [...prev, novoTurno()]);
  }

  function removeTurno(index) {
    setTurnos((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true); setSavedMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(turnos),
      });
      setSavedMsg(res.ok ? "Turnos salvos com sucesso!" : "Erro ao salvar.");
    } catch { setSavedMsg("Erro de conexão."); }
    finally { setSaving(false); setTimeout(() => setSavedMsg(""), 4000); }
  }

  return (
    <div className="cfg-card">
      <div className="cfg-card-header">
        <div className="cfg-card-title-row">
          <span className="cfg-card-title">Gestão de Turnos</span>
          <div className="cfg-card-header-right">
            {savedMsg && <span className="cfg-saved-msg">{savedMsg}</span>}
            <button className="cfg-save-btn" onClick={handleSave} disabled={saving || !selectedId}>
              {saving ? "Salvando..." : "Salvar Turnos"}
            </button>
          </div>
        </div>
        <p className="cfg-card-desc">
          Turnos são definidos por linha de produção. Você pode ter múltiplos turnos por dia.
          Todas as máquinas da linha seguem o mesmo calendário.
        </p>
      </div>

      <div className="cfg-field-group" style={{ marginBottom: 20 }}>
        <label className="cfg-label">Linha de Produção</label>
        <select className="cfg-select" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
          {linhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
      </div>

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {!loading && (
        <>
          {/* Header */}
          <div className="cfg-shift-header">
            <span>Dia</span>
            <span>Nome do Turno</span>
            <span>Início</span>
            <span>Fim</span>
            <span className="cfg-shift-status-col">Status</span>
            <span />
          </div>

          {/* Lista de turnos */}
          {turnos.length === 0 && (
            <div className="cfg-shift-empty">
              Nenhum turno configurado. Clique em "Adicionar Turno" para começar.
            </div>
          )}

          {turnos.map((turno, i) => {
            const isToday = turno.dia === TODAY_NAME;
            return (
              <div
                key={i}
                className={["cfg-shift-row", !turno.ativo ? "cfg-shift-row--inactive" : "", isToday ? "cfg-shift-row--today" : ""].join(" ")}
              >
                {/* Dia */}
                <div className="cfg-shift-dia">
                  <select
                    className="cfg-dia-select"
                    value={turno.dia}
                    onChange={(e) => setField(i, "dia", e.target.value)}
                  >
                    {DIAS_SEMANA.map((d) => (
                      <option key={d} value={d}>{DIAS_SHORT[d]}</option>
                    ))}
                  </select>
                  {isToday && <span className="cfg-hoje-tag">hoje</span>}
                </div>

                {/* Nome */}
                <input
                  className="cfg-shift-name-input"
                  type="text"
                  value={turno.nome ?? ""}
                  placeholder="Ex: Manhã"
                  onChange={(e) => setField(i, "nome", e.target.value)}
                />

                {/* Início */}
                <input
                  className="cfg-time-input"
                  type="time"
                  value={turno.inicio}
                  onChange={(e) => setField(i, "inicio", e.target.value)}
                />

                {/* Fim */}
                <input
                  className="cfg-time-input"
                  type="time"
                  value={turno.fim}
                  onChange={(e) => setField(i, "fim", e.target.value)}
                />

                {/* Toggle */}
                <div className="cfg-toggle-wrap">
                  <span className="cfg-toggle-label">{turno.ativo ? "Ativo" : "Inativo"}</span>
                  <button
                    type="button"
                    className={`cfg-toggle${turno.ativo ? " cfg-toggle--on" : ""}`}
                    onClick={() => setField(i, "ativo", !turno.ativo)}
                  >
                    <span className="cfg-toggle-knob" />
                  </button>
                </div>

                {/* Remover */}
                <button type="button" className="cfg-remove-btn" onClick={() => removeTurno(i)} title="Remover turno">
                  ✕
                </button>
              </div>
            );
          })}

          {/* Botão adicionar */}
          <button type="button" className="cfg-add-btn" onClick={addTurno}>
            + Adicionar Turno
          </button>
        </>
      )}
    </div>
  );
}

/* ── Seção: Parâmetros de Máquina ────────────────────────── */
function ParametrosMaquina() {
  const [machines, setMachines]                 = useState([]);
  const [selectedId, setSelectedId]             = useState(null);
  const [config, setConfig]                     = useState(null);
  const [meta, setMeta]                         = useState(0);
  const [peca, setPeca]                         = useState("");
  const [producaoTeorica, setProducaoTeorica]   = useState(0);
  const [saving, setSaving]                     = useState(false);
  const [savedMsg, setSavedMsg]                 = useState("");
  const [loading, setLoading]                   = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/config/machines`)
      .then((r) => r.json())
      .then((data) => { setMachines(data); if (data.length > 0) setSelectedId(data[0].id); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setConfig(null); setLoading(true);
    fetch(`${API_BASE}/api/config/machines/${selectedId}`)
      .then((r) => r.json())
      .then((data) => {
        setConfig(data);
        setMeta(data.meta ?? 0);
        setPeca(data.peca_atual ?? "");
        setProducaoTeorica(data.producao_teorica ?? 0);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedId]);

  async function handleSave() {
    if (!selectedId || !config) return;
    setSaving(true); setSavedMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/config/machines/${selectedId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meta, peca, producao_teorica: producaoTeorica }),
      });
      setSavedMsg(res.ok ? "Parâmetros salvos!" : "Erro ao salvar.");
    } catch { setSavedMsg("Erro de conexão."); }
    finally { setSaving(false); setTimeout(() => setSavedMsg(""), 4000); }
  }

  const st = config ? statusStyle(config.status) : {};

  return (
    <div className="cfg-card cfg-params-card">
      <div className="cfg-card-header">
        <div className="cfg-card-title-row">
          <span className="cfg-card-title">Parâmetros de Máquina</span>
          <div className="cfg-card-header-right">
            {savedMsg && <span className="cfg-saved-msg">{savedMsg}</span>}
          </div>
        </div>
        <p className="cfg-card-desc">Meta e peça são configurados individualmente por máquina.</p>
      </div>

      <div className="cfg-field-group" style={{ marginBottom: 16 }}>
        <label className="cfg-label">Selecione a Máquina</label>
        <select className="cfg-select" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
          {machines.map((m) => <option key={m.id} value={m.id}>{m.nome} ({m.linha})</option>)}
        </select>
      </div>

      {config && (
        <div className="cfg-status-group" style={{ marginBottom: 16 }}>
          <span className="cfg-label">Status Atual</span>
          <div className="cfg-status-row">
            <span className="cfg-status-badge" style={{ color: st.color, background: st.bg }}>{config.status}</span>
            <span className="cfg-status-desde">desde {config.status_desde}</span>
          </div>
        </div>
      )}

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {config && !loading && (
        <>
          <div className="cfg-ctx-section">
            <label className="cfg-label">Peça / Produto</label>
            <select className="cfg-select" value={peca} onChange={(e) => setPeca(e.target.value)}>
              {(config.pecas ?? []).map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div className="cfg-ctx-section">
            <span className="cfg-label">Produção Teórica (pç/h)</span>
            <p className="cfg-field-hint">
              Capacidade máxima da máquina. Usada para calcular automaticamente a meta de cada turno nas Ordens de Produção.
            </p>
            <div className="cfg-meta-ctrl">
              <button className="cfg-meta-btn" type="button" onClick={() => setProducaoTeorica((v) => Math.max(0, v - 1))}>−</button>
              <input className="cfg-meta-input" type="number" min={0} value={producaoTeorica} onChange={(e) => setProducaoTeorica(Number(e.target.value))} />
              <button className="cfg-meta-btn" type="button" onClick={() => setProducaoTeorica((v) => v + 1)}>+</button>
            </div>
          </div>

          <div className="cfg-ctx-section">
            <span className="cfg-label">Meta de Produção (turno atual)</span>
            <p className="cfg-field-hint">
              Ajuste manual da meta do turno em curso. Normalmente preenchida automaticamente pelas Ordens de Produção.
            </p>
            <div className="cfg-meta-ctrl">
              <button className="cfg-meta-btn" type="button" onClick={() => setMeta((m) => Math.max(0, m - 1))}>−</button>
              <input className="cfg-meta-input" type="number" min={0} value={meta} onChange={(e) => setMeta(Number(e.target.value))} />
              <button className="cfg-meta-btn" type="button" onClick={() => setMeta((m) => m + 1)}>+</button>
            </div>
            <button className="cfg-ajustar-btn" type="button" onClick={handleSave} disabled={saving}>
              {saving ? "Salvando..." : "Salvar Parâmetros"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Página principal ────────────────────────────────────── */
export default function Configuracoes() {
  return (
    <div className="cfg-root">
      <div className="cfg-topbar">
        <div>
          <h1 className="cfg-page-title">Configurações</h1>
          <p className="cfg-page-sub">Gerencie turnos por linha de produção e parâmetros individuais de cada máquina.</p>
        </div>
      </div>

      <div className="cfg-two-col">
        <GestaoTurnos />
        <ParametrosMaquina />
      </div>
    </div>
  );
}
