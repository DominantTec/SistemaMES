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

const DIAS_SHORT = {
  "Segunda": "Seg", "Terça": "Ter", "Quarta": "Qua",
  "Quinta": "Qui", "Sexta": "Sex", "Sábado": "Sáb", "Domingo": "Dom",
};

const TODAY_DOW = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;

function statusStyle(s) {
  return STATUS_STYLE[s] || { color: "#6b7280", bg: "#f3f4f6" };
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
      .then((data) => setTurnos(data.calendario ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedId]);

  function setTurnoField(index, field, value) {
    setTurnos((prev) => prev.map((d, i) => (i === index ? { ...d, [field]: value } : d)));
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
          Turnos são definidos por linha de produção. Todas as máquinas de uma linha seguem o mesmo calendário.
        </p>
      </div>

      <div className="cfg-field-group" style={{ marginBottom: 20 }}>
        <label className="cfg-label">Linha de Produção</label>
        <select className="cfg-select" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
          {linhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
      </div>

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {!loading && turnos.length > 0 && (
        <>
          <div className="cfg-shift-header">
            <span>Dia</span>
            <span>Nome do Turno</span>
            <span>Início</span>
            <span>Fim</span>
            <span className="cfg-shift-status-col">Status</span>
          </div>

          {turnos.map((turno, i) => {
            const isToday = i === TODAY_DOW;
            return (
              <div key={turno.dia} className={["cfg-shift-row", !turno.ativo ? "cfg-shift-row--inactive" : "", isToday ? "cfg-shift-row--today" : ""].join(" ")}>
                <div className="cfg-shift-dia">
                  <span className={`cfg-dia-pill${isToday ? " cfg-dia-pill--today" : ""}`}>{DIAS_SHORT[turno.dia] ?? turno.dia}</span>
                  {isToday && <span className="cfg-hoje-tag">hoje</span>}
                </div>
                <input className="cfg-shift-name-input" type="text" value={turno.nome ?? ""} disabled={!turno.ativo} placeholder="Ex: Turno 1" onChange={(e) => setTurnoField(i, "nome", e.target.value)} />
                <input className="cfg-time-input" type="time" value={turno.inicio} disabled={!turno.ativo} onChange={(e) => setTurnoField(i, "inicio", e.target.value)} />
                <input className="cfg-time-input" type="time" value={turno.fim} disabled={!turno.ativo} onChange={(e) => setTurnoField(i, "fim", e.target.value)} />
                <div className="cfg-toggle-wrap">
                  <span className="cfg-toggle-label">{turno.ativo ? "Ativo" : "Inativo"}</span>
                  <button type="button" className={`cfg-toggle${turno.ativo ? " cfg-toggle--on" : ""}`} onClick={() => setTurnoField(i, "ativo", !turno.ativo)}>
                    <span className="cfg-toggle-knob" />
                  </button>
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

/* ── Seção: Parâmetros de Máquina ────────────────────────── */
function ParametrosMaquina() {
  const [machines, setMachines]     = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [config, setConfig]         = useState(null);
  const [meta, setMeta]             = useState(0);
  const [peca, setPeca]             = useState("");
  const [saving, setSaving]         = useState(false);
  const [savedMsg, setSavedMsg]     = useState("");
  const [loading, setLoading]       = useState(false);

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
      .then((data) => { setConfig(data); setMeta(data.meta ?? 0); setPeca(data.peca_atual ?? ""); })
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
        body: JSON.stringify({ meta, peca }),
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
            <span className="cfg-label">Meta de Produção</span>
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
