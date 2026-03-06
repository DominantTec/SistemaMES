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

function statusStyle(s) {
  return STATUS_STYLE[s] || { color: "#6b7280", bg: "#f3f4f6" };
}

export default function Configuracoes() {
  const [machines, setMachines]     = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [config, setConfig]         = useState(null);
  const [meta, setMeta]             = useState(0);
  const [peca, setPeca]             = useState("");
  const [calendario, setCalendario] = useState([]);
  const [saving, setSaving]         = useState(false);
  const [savedMsg, setSavedMsg]     = useState("");
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/config/machines`)
      .then((r) => r.json())
      .then((data) => {
        setMachines(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setConfig(null);
    setLoading(true);
    fetch(`${API_BASE}/api/config/machines/${selectedId}`)
      .then((r) => r.json())
      .then((data) => {
        setConfig(data);
        setMeta(data.meta ?? 0);
        setPeca(data.peca_atual ?? "");
        setCalendario(data.calendario ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedId]);

  function setDiaField(index, field, value) {
    setCalendario((prev) =>
      prev.map((d, i) => (i === index ? { ...d, [field]: value } : d))
    );
  }

  async function handleSave() {
    if (!selectedId || !config) return;
    setSaving(true);
    setSavedMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/config/machines/${selectedId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meta, peca, calendario }),
      });
      if (res.ok) {
        setSavedMsg("Alterações salvas com sucesso!");
      } else {
        setSavedMsg("Erro ao salvar. Tente novamente.");
      }
      setTimeout(() => setSavedMsg(""), 4000);
    } catch {
      setSavedMsg("Erro de conexão.");
      setTimeout(() => setSavedMsg(""), 4000);
    } finally {
      setSaving(false);
    }
  }

  const st = config ? statusStyle(config.status) : {};

  return (
    <div className="cfg-root">

      {/* Topbar */}
      <div className="cfg-topbar">
        <div>
          <h1 className="cfg-page-title">Parâmetros de Produção</h1>
          <p className="cfg-page-sub">Gerencie metas, turnos e alocação de operadores por recurso.</p>
        </div>
        <div className="cfg-topbar-right">
          {savedMsg && <span className="cfg-saved-msg">{savedMsg}</span>}
          <button
            className="cfg-save-btn"
            onClick={handleSave}
            disabled={saving || !config}
          >
            {saving ? "Salvando..." : "Salvar Alterações"}
          </button>
        </div>
      </div>

      {/* Machine selector card */}
      <div className="cfg-card cfg-selector-card">
        <div className="cfg-field-group">
          <label className="cfg-label">Selecione a Máquina</label>
          <select
            className="cfg-select"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {machines.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome} ({m.linha})
              </option>
            ))}
          </select>
        </div>

        {config && (
          <div className="cfg-status-group">
            <span className="cfg-label">Status Atual</span>
            <div className="cfg-status-row">
              <span
                className="cfg-status-badge"
                style={{ color: st.color, background: st.bg }}
              >
                {config.status}
              </span>
              <span className="cfg-status-desde">desde {config.status_desde}</span>
            </div>
          </div>
        )}
      </div>

      {loading && (
        <div className="cfg-loading">
          <div className="cfg-spinner" /> Carregando...
        </div>
      )}

      {config && !loading && (
        <div className="cfg-body">

          {/* Left: Calendar */}
          <div className="cfg-left">
            <div className="cfg-card">
              <div className="cfg-card-header">
                <span className="cfg-card-title">Calendário de Funcionamento</span>
              </div>

              <div className="cfg-cal-header-row">
                <span>Dia</span>
                <span>Início</span>
                <span>Fim</span>
                <span className="cfg-cal-status-col">Status</span>
              </div>

              {calendario.map((dia, i) => (
                <div
                  key={dia.dia}
                  className={`cfg-cal-row${!dia.ativo ? " cfg-cal-row--inactive" : ""}`}
                >
                  <span className="cfg-cal-dia">{dia.dia}</span>

                  <input
                    className="cfg-time-input"
                    type="time"
                    value={dia.inicio}
                    disabled={!dia.ativo}
                    onChange={(e) => setDiaField(i, "inicio", e.target.value)}
                  />

                  <span className="cfg-cal-sep">–</span>

                  <input
                    className="cfg-time-input"
                    type="time"
                    value={dia.fim}
                    disabled={!dia.ativo}
                    onChange={(e) => setDiaField(i, "fim", e.target.value)}
                  />

                  <div className="cfg-toggle-wrap">
                    <span className="cfg-toggle-label">
                      {dia.ativo ? "Ativo" : "Inativo"}
                    </span>
                    <button
                      type="button"
                      className={`cfg-toggle${dia.ativo ? " cfg-toggle--on" : ""}`}
                      onClick={() => setDiaField(i, "ativo", !dia.ativo)}
                    >
                      <span className="cfg-toggle-knob" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Context */}
          <div className="cfg-right">
            <div className="cfg-card cfg-ctx-card">
              <div className="cfg-ctx-header">
                <span className="cfg-card-title">Contexto Atual</span>
              </div>

              <div className="cfg-ctx-section">
                <label className="cfg-label">Peça / Produto</label>
                <select
                  className="cfg-select"
                  value={peca}
                  onChange={(e) => setPeca(e.target.value)}
                >
                  {(config.pecas ?? []).map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              <div className="cfg-ctx-section">
                <div className="cfg-label-row">
                  <span className="cfg-label">Meta de Produção</span>
                </div>
                <div className="cfg-meta-ctrl">
                  <button
                    className="cfg-meta-btn"
                    type="button"
                    onClick={() => setMeta((m) => Math.max(0, m - 1))}
                  >
                    −
                  </button>
                  <input
                    className="cfg-meta-input"
                    type="number"
                    min={0}
                    value={meta}
                    onChange={(e) => setMeta(Number(e.target.value))}
                  />
                  <button
                    className="cfg-meta-btn"
                    type="button"
                    onClick={() => setMeta((m) => m + 1)}
                  >
                    +
                  </button>
                </div>
                <button
                  className="cfg-ajustar-btn"
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                >
                  Ajustar Meta
                </button>
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
