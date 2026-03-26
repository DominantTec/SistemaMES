import { useEffect, useState } from "react";
import "./Configuracoes.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

const DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
const DIAS_SHORT  = { "Segunda": "Seg", "Terça": "Ter", "Quarta": "Qua", "Quinta": "Qui", "Sexta": "Sex", "Sábado": "Sáb", "Domingo": "Dom" };
const TODAY_NAME  = DIAS_SEMANA[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1];
const TODAY_IDX   = DIAS_SEMANA.indexOf(TODAY_NAME);

function novoTurno() {
  return { dia: TODAY_NAME, nome: "", inicio: "07:00", fim: "15:00", ativo: true };
}

/* ── Seção: Gestão de Turnos ─────────────────────────────── */
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
    <div className="cfg-section">
      {/* Linha de produção */}
      <div className="cfg-row-between cfg-mb16">
        <div className="cfg-field-group" style={{ flex: 1, maxWidth: 340 }}>
          <label className="cfg-label">Linha de Produção</label>
          <select className="cfg-select" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
            {linhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        </div>
        <div className="cfg-row-end" style={{ gap: 12 }}>
          {savedMsg && <span className="cfg-saved-msg">{savedMsg}</span>}
          <button className="cfg-save-btn" onClick={handleSave} disabled={saving || !selectedId}>
            {saving ? "Salvando..." : "Salvar Turnos"}
          </button>
        </div>
      </div>

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {!loading && (
        <>
          <div className="cfg-shift-header">
            <span>Dia</span>
            <span>Nome do Turno</span>
            <span>Início</span>
            <span>Fim</span>
            <span className="cfg-shift-status-col">Status</span>
            <span />
          </div>

          {turnos.filter(t => DIAS_SEMANA.indexOf(t.dia) >= TODAY_IDX).length === 0 && (
            <div className="cfg-shift-empty">
              Nenhum turno configurado a partir de hoje. Clique em "Adicionar Turno" para começar.
            </div>
          )}

          {turnos.map((turno, i) => {
            if (DIAS_SEMANA.indexOf(turno.dia) < TODAY_IDX) return null;
            const isToday = turno.dia === TODAY_NAME;
            return (
              <div
                key={i}
                className={["cfg-shift-row", !turno.ativo ? "cfg-shift-row--inactive" : "", isToday ? "cfg-shift-row--today" : ""].join(" ")}
              >
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

                <input
                  className="cfg-shift-name-input"
                  type="text"
                  value={turno.nome ?? ""}
                  placeholder="Ex: Manhã"
                  onChange={(e) => setField(i, "nome", e.target.value)}
                />

                <input
                  className="cfg-time-input"
                  type="time"
                  value={turno.inicio}
                  onChange={(e) => setField(i, "inicio", e.target.value)}
                />

                <input
                  className="cfg-time-input"
                  type="time"
                  value={turno.fim}
                  onChange={(e) => setField(i, "fim", e.target.value)}
                />

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

                <button type="button" className="cfg-remove-btn" onClick={() => removeTurno(i)} title="Remover turno">
                  ✕
                </button>
              </div>
            );
          })}

          <button type="button" className="cfg-add-btn" onClick={addTurno}>
            + Adicionar Turno
          </button>
        </>
      )}
    </div>
  );
}

/* ── Seção: Peças e Roteiros ─────────────────────────────── */
function GestaoPecas() {
  const [linhas, setLinhas]             = useState([]);
  const [selectedLinha, setSelectedLinha] = useState(null);
  const [pecas, setPecas]               = useState([]);
  const [selectedPeca, setSelectedPeca] = useState(null);
  const [maquinas, setMaquinas]         = useState([]);
  const [rota, setRota]                 = useState([]);
  const [novaNome, setNovaNome]         = useState("");
  const [addingPeca, setAddingPeca]     = useState(false);
  const [addMsg, setAddMsg]             = useState("");
  const [saving, setSaving]             = useState(false);
  const [savedMsg, setSavedMsg]         = useState("");
  const [loading, setLoading]           = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then(r => r.json())
      .then(data => { setLinhas(data); if (data.length > 0) setSelectedLinha(data[0].id); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedLinha) return;
    setLoading(true);
    setSelectedPeca(null);
    Promise.all([
      fetch(`${API_BASE}/api/config/lines/${selectedLinha}/pecas`).then(r => r.json()),
      fetch(`${API_BASE}/api/config/lines/${selectedLinha}/machines`).then(r => r.json()),
    ])
      .then(([p, m]) => { setPecas(p); setMaquinas(m); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedLinha]);

  useEffect(() => {
    if (!selectedPeca) { setRota([]); return; }
    const found = pecas.find(p => p.id === selectedPeca);
    if (found) setRota(found.rota);
  }, [selectedPeca, pecas]);

  async function handleAddPeca() {
    if (!novaNome.trim() || !selectedLinha) return;
    setAddingPeca(true); setAddMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/config/lines/${selectedLinha}/pecas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: novaNome.trim() }),
      });
      if (res.ok) {
        const nova = await res.json();
        setPecas(prev => [...prev, nova]);
        setSelectedPeca(nova.id);
        setNovaNome("");
      } else {
        const err = await res.json().catch(() => ({}));
        setAddMsg(err.detail || "Erro ao adicionar peça.");
        setTimeout(() => setAddMsg(""), 4000);
      }
    } catch {
      setAddMsg("Erro de conexão.");
      setTimeout(() => setAddMsg(""), 4000);
    } finally {
      setAddingPeca(false);
    }
  }

  async function handleDeletePeca(pecaId) {
    if (!window.confirm("Excluir esta peça e seu roteiro?")) return;
    await fetch(`${API_BASE}/api/config/pecas/${pecaId}`, { method: "DELETE" });
    setPecas(prev => prev.filter(p => p.id !== pecaId));
    if (selectedPeca === pecaId) setSelectedPeca(null);
  }

  async function handleSaveRota() {
    if (!selectedPeca) return;
    setSaving(true); setSavedMsg("");
    try {
      const steps = rota.map(m => ({ id_ihm: m.id_ihm, producao_teorica: m.producao_teorica ?? 0 }));
      const res = await fetch(`${API_BASE}/api/config/pecas/${selectedPeca}/rota`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ steps }),
      });
      if (res.ok) {
        setSavedMsg("Roteiro salvo!");
        setPecas(prev => prev.map(p => p.id === selectedPeca ? { ...p, rota } : p));
      } else {
        setSavedMsg("Erro ao salvar.");
      }
    } catch { setSavedMsg("Erro de conexão."); }
    finally { setSaving(false); setTimeout(() => setSavedMsg(""), 3000); }
  }

  function addToRota(maquina) {
    if (rota.find(m => m.id_ihm === maquina.id)) return;
    setRota(prev => [...prev, { id_ihm: maquina.id, nome: maquina.nome, nu_ordem: prev.length + 1, producao_teorica: 0 }]);
  }

  function removeFromRota(id_ihm) {
    setRota(prev => prev.filter(m => m.id_ihm !== id_ihm).map((m, i) => ({ ...m, nu_ordem: i + 1 })));
  }

  function setRotaProd(id_ihm, value) {
    setRota(prev => prev.map(m => m.id_ihm === id_ihm ? { ...m, producao_teorica: value } : m));
  }

  function moveUp(idx) {
    if (idx === 0) return;
    setRota(prev => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next.map((m, i) => ({ ...m, nu_ordem: i + 1 }));
    });
  }

  function moveDown(idx) {
    setRota(prev => {
      if (idx === prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next.map((m, i) => ({ ...m, nu_ordem: i + 1 }));
    });
  }

  const rotaIds = new Set(rota.map(m => m.id_ihm));
  const maquinasDisponiveis = maquinas.filter(m => !rotaIds.has(m.id));

  return (
    <div className="cfg-section">
      {/* Linha de produção */}
      <div className="cfg-row-between cfg-mb16">
        <div className="cfg-field-group" style={{ flex: 1, maxWidth: 340 }}>
          <label className="cfg-label">Linha de Produção</label>
          <select className="cfg-select" value={selectedLinha ?? ""} onChange={e => setSelectedLinha(Number(e.target.value))}>
            {linhas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        </div>
        {selectedPeca && (
          <div className="cfg-row-end" style={{ gap: 12 }}>
            {savedMsg && <span className="cfg-saved-msg">{savedMsg}</span>}
            <button className="cfg-save-btn" onClick={handleSaveRota} disabled={saving}>
              {saving ? "Salvando..." : "Salvar Roteiro"}
            </button>
          </div>
        )}
      </div>

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {!loading && (
        <div className="cfg-pecas-layout">

          {/* Coluna esquerda: lista de peças */}
          <div className="cfg-pecas-list-col">
            <div className="cfg-col-title">Peças Configuradas</div>

            {pecas.length === 0 && (
              <div className="cfg-shift-empty">Nenhuma peça configurada para esta linha.</div>
            )}

            {pecas.map(p => (
              <div
                key={p.id}
                className={`cfg-peca-item${selectedPeca === p.id ? " cfg-peca-item--selected" : ""}`}
                onClick={() => setSelectedPeca(p.id)}
              >
                <span className="cfg-peca-nome">{p.nome}</span>
                <div className="cfg-peca-meta">
                  <span className="cfg-peca-rota-count">{p.rota.length} máq.</span>
                  <button
                    type="button"
                    className="cfg-remove-btn"
                    onPointerDown={e => e.stopPropagation()}
                    onClick={e => { e.stopPropagation(); handleDeletePeca(p.id); }}
                  >✕</button>
                </div>
              </div>
            ))}

            <div className="cfg-add-peca-row">
              <input
                className="cfg-shift-name-input"
                placeholder="Nome da nova peça..."
                value={novaNome}
                onChange={e => setNovaNome(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleAddPeca()}
              />
              <button
                type="button"
                className="cfg-save-btn"
                style={{ whiteSpace: "nowrap", padding: "9px 16px" }}
                onClick={handleAddPeca}
                disabled={!novaNome.trim() || !selectedLinha || addingPeca}
              >
                {addingPeca ? "..." : "+ Adicionar"}
              </button>
            </div>
            {addMsg && <div className="cfg-error-msg">{addMsg}</div>}
          </div>

          {/* Coluna direita: editor de roteiro */}
          {selectedPeca ? (
            <div className="cfg-rota-col">
              <div className="cfg-col-title">
                Roteiro — {pecas.find(p => p.id === selectedPeca)?.nome}
              </div>

              {rota.length === 0 && (
                <div className="cfg-shift-empty">Nenhuma máquina no roteiro. Adicione abaixo.</div>
              )}

              {rota.map((m, idx) => (
                <div key={m.id_ihm} className="cfg-rota-item">
                  <span className="cfg-rota-ordem">{idx + 1}</span>
                  <span className="cfg-rota-nome">{m.nome}</span>
                  <div className="cfg-rota-prod">
                    <input
                      className="cfg-rota-prod-input"
                      type="number"
                      min={0}
                      value={m.producao_teorica ?? 0}
                      onChange={e => setRotaProd(m.id_ihm, Number(e.target.value))}
                      title="Produção Teórica (pç/h)"
                    />
                    <span className="cfg-rota-prod-unit">pç/h</span>
                  </div>
                  <div className="cfg-rota-actions">
                    <button type="button" className="cfg-rota-btn" onClick={() => moveUp(idx)} disabled={idx === 0}>↑</button>
                    <button type="button" className="cfg-rota-btn" onClick={() => moveDown(idx)} disabled={idx === rota.length - 1}>↓</button>
                    <button type="button" className="cfg-remove-btn" onClick={() => removeFromRota(m.id_ihm)}>✕</button>
                  </div>
                </div>
              ))}

              {maquinasDisponiveis.length > 0 && (
                <>
                  <div className="cfg-rota-disponivel-label">Disponíveis para adicionar:</div>
                  {maquinasDisponiveis.map(m => (
                    <div key={m.id} className="cfg-rota-disponivel-item" onClick={() => addToRota(m)}>
                      <span>{m.nome}</span>
                      <span className="cfg-rota-add-btn">+ Adicionar</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          ) : (
            <div className="cfg-rota-col cfg-rota-empty">
              Selecione uma peça para configurar seu roteiro.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Página principal ────────────────────────────────────── */
export default function Configuracoes() {
  const [tab, setTab] = useState("turnos");

  return (
    <div className="cfg-root">
      <div className="cfg-topbar">
        <div>
          <h1 className="cfg-page-title">Configurações</h1>
          <p className="cfg-page-sub">Gerencie turnos, peças e roteiros por linha de produção.</p>
        </div>
      </div>

      <div className="cfg-tabs">
        <button
          className={`cfg-tab${tab === "turnos" ? " cfg-tab--active" : ""}`}
          onClick={() => setTab("turnos")}
        >
          Turnos de Trabalho
        </button>
        <button
          className={`cfg-tab${tab === "pecas" ? " cfg-tab--active" : ""}`}
          onClick={() => setTab("pecas")}
        >
          Peças e Roteiros
        </button>
      </div>

      <div className="cfg-card">
        {tab === "turnos" && <GestaoTurnos />}
        {tab === "pecas"  && <GestaoPecas />}
      </div>
    </div>
  );
}
