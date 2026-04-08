import React, { useEffect, useState } from "react";
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

/* ── Seção: Controle de Turno (Gerente) ─────────────────── */
function ControleTurno() {
  const [linhas, setLinhas]       = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [turnos, setTurnos]       = useState([]);
  const [loading, setLoading]     = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then((r) => r.json())
      .then((data) => { setLinhas(data); if (data.length > 0) setSelectedId(data[0].id); })
      .catch(() => {});
  }, []);

  function fetchTurnos(lineId) {
    if (!lineId) return;
    setLoading(true);
    fetch(`${API_BASE}/api/config/lines/${lineId}/turnos/proximos`)
      .then((r) => r.json())
      .then((data) => { setTurnos(data); setLoading(false); })
      .catch(() => setLoading(false));
  }

  useEffect(() => { fetchTurnos(selectedId); }, [selectedId]);

  async function handleAction(id, acao) {
    setActionMsg("");
    const res = await fetch(`${API_BASE}/api/config/turnos/${id}/${acao}`, { method: "POST" });
    const body = await res.json().catch(() => ({}));
    if (res.ok) {
      setActionMsg(acao === "iniciar" ? "Turno iniciado!" : "Turno finalizado!");
      fetchTurnos(selectedId);
    } else {
      setActionMsg(body.detail || "Erro ao executar ação.");
    }
    setTimeout(() => setActionMsg(""), 4000);
  }

  function fmtDT(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  const STATUS_LABEL = { em_andamento: "Em andamento", agendado: "Agendado", finalizado: "Finalizado" };
  const STATUS_COLOR = { em_andamento: "#16a34a", agendado: "#3b82f6", finalizado: "#6b7280" };

  return (
    <div className="cfg-section">
      <div className="cfg-row-between cfg-mb16">
        <div className="cfg-field-group" style={{ flex: 1, maxWidth: 340 }}>
          <label className="cfg-label">Linha de Produção</label>
          <select className="cfg-select" value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
            {linhas.map((l) => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        </div>
        {actionMsg && (
          <div style={{ alignSelf: "flex-end", marginBottom: 2 }}>
            <span className="cfg-saved-msg">{actionMsg}</span>
          </div>
        )}
      </div>

      {loading && <div className="cfg-loading"><div className="cfg-spinner" /> Carregando...</div>}

      {!loading && turnos.length === 0 && (
        <div className="cfg-shift-empty">Nenhum turno pendente para esta linha.</div>
      )}

      {!loading && turnos.length > 0 && (
        <div className="cfg-ctrl-list">
          {turnos.map((t) => {
            const cor = STATUS_COLOR[t.status] || "#6b7280";
            const isActive = t.status === "em_andamento";
            const isAgendado = t.status === "agendado";
            const dtRealInicio = t.dt_real_inicio ? fmtDT(t.dt_real_inicio) : null;
            const dtRealFim    = t.dt_real_fim    ? fmtDT(t.dt_real_fim)    : null;
            return (
              <div key={t.id_ocorrencia} className={`cfg-ctrl-row${isActive ? " cfg-ctrl-row--ativo" : ""}`}>
                <div className="cfg-ctrl-info">
                  <span className="cfg-ctrl-nome">{t.nome}</span>
                  <span className="cfg-ctrl-status" style={{ color: cor }}>
                    {STATUS_LABEL[t.status] || t.status}
                  </span>
                  <span className="cfg-ctrl-horarios">
                    Previsto: {fmtDT(t.dt_inicio)} – {fmtDT(t.dt_fim)}
                  </span>
                  {dtRealInicio && (
                    <span className="cfg-ctrl-horarios cfg-ctrl-real">
                      Real: {dtRealInicio}{dtRealFim ? ` – ${dtRealFim}` : " (em curso)"}
                    </span>
                  )}
                  {t.status === "finalizado" && (
                    <span className="cfg-ctrl-prod">
                      Produzido: <strong>{t.produzido}</strong> / Meta: {t.meta}
                    </span>
                  )}
                </div>
                <div className="cfg-ctrl-actions">
                  {isAgendado && (
                    <button
                      className="cfg-ctrl-btn cfg-ctrl-btn--iniciar"
                      onClick={() => handleAction(t.id_ocorrencia, "iniciar")}
                    >
                      Iniciar Turno
                    </button>
                  )}
                  {isActive && (
                    <button
                      className="cfg-ctrl-btn cfg-ctrl-btn--finalizar"
                      onClick={() => handleAction(t.id_ocorrencia, "finalizar")}
                    >
                      Finalizar Turno
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Seção: Gestão de Turnos ─────────────────────────────── */
function GestaoTurnos() {
  const [linhas, setLinhas]         = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [turnos, setTurnos]         = useState([]);
  const [saving, setSaving]         = useState(false);
  const [savedMsg, setSavedMsg]     = useState("");
  const [loading, setLoading]       = useState(false);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [vinculMsg,   setVinculMsg]   = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/config/lines`)
      .then((r) => r.json())
      .then((data) => { setLinhas(data); if (data.length > 0) setSelectedId(data[0].id); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setExpandedIdx(null);
    fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`)
      .then((r) => r.json())
      .then((data) => setTurnos(data.turnos ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedId]);

  function setField(index, field, value) {
    setTurnos((prev) => prev.map((t, i) => (i === index ? { ...t, [field]: value } : t)));
  }

  function toggleLinha(index, linhaId) {
    setTurnos((prev) => prev.map((t, i) => {
      if (i !== index) return t;
      const cur = t.linha_ids || [];
      const next = cur.includes(linhaId)
        ? cur.filter((x) => x !== linhaId)
        : [...cur, linhaId];
      // garante ao menos a linha atual selecionada
      return { ...t, linha_ids: next.length === 0 ? [selectedId] : next };
    }));
  }

  async function saveVincular(idx, idModelo) {
    const t = turnos[idx];
    const ids = (t.linha_ids && t.linha_ids.length > 0) ? t.linha_ids : [selectedId];
    setVinculMsg("Salvando...");
    try {
      const res = await fetch(`${API_BASE}/api/config/turno-modelos/${idModelo}/linhas`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ linha_ids: ids }),
      });
      if (res.ok) {
        setVinculMsg("Vínculos salvos!");
        const data = await fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`).then((r) => r.json());
        setTurnos(data.turnos ?? []);
        setTimeout(() => { setVinculMsg(""); setExpandedIdx(null); }, 1800);
      } else {
        const body = await res.json().catch(() => ({}));
        setVinculMsg(body.detail || "Erro ao salvar.");
      }
    } catch { setVinculMsg("Erro de conexão."); }
  }

  function addTurno() {
    setTurnos((prev) => [...prev, { dia: TODAY_NAME, nome: "", inicio: "07:00", fim: "15:00", ativo: true, linha_ids: [selectedId] }]);
  }

  function removeTurno(index) {
    setTurnos((prev) => prev.filter((_, i) => i !== index));
    if (expandedIdx === index) setExpandedIdx(null);
  }

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true); setSavedMsg("");
    try {
      const payload = turnos.map((t) => ({
        ...t,
        linha_ids: (t.linha_ids && t.linha_ids.length > 0) ? t.linha_ids : [selectedId],
      }));
      const res = await fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setSavedMsg("Turnos salvos com sucesso!");
        // Recarrega para obter id_modelos atualizados
        const data = await fetch(`${API_BASE}/api/config/lines/${selectedId}/turnos`).then((r) => r.json());
        setTurnos(data.turnos ?? []);
      } else {
        setSavedMsg("Erro ao salvar.");
      }
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
            <span title="Linhas vinculadas">Linhas</span>
            <span />
          </div>

          {turnos.length === 0 && (
            <div className="cfg-shift-empty">
              Nenhum turno configurado. Clique em "Adicionar Turno" para começar.
            </div>
          )}

          {turnos.map((turno, i) => {
            const isToday = turno.dia === TODAY_NAME;
            const linhasVinc = (turno.linha_ids || [selectedId]).filter(Boolean);
            const isExpanded = expandedIdx === i;
            return (
              <React.Fragment key={i}>
                <div
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

                  {/* Botão de linhas vinculadas */}
                  <button
                    type="button"
                    className={`cfg-linhas-btn${isExpanded ? " cfg-linhas-btn--active" : ""}`}
                    onClick={() => setExpandedIdx(isExpanded ? null : i)}
                    title="Vincular a linhas de produção"
                  >
                    {linhasVinc.length} {linhasVinc.length === 1 ? "linha" : "linhas"}
                  </button>

                  <button type="button" className="cfg-remove-btn" onClick={() => removeTurno(i)} title="Remover turno">
                    ✕
                  </button>
                </div>

                {/* Painel inline de seleção de linhas */}
                {isExpanded && (
                  <div className="cfg-linhas-panel">
                    <span className="cfg-linhas-panel-title">Linhas que seguem este turno:</span>
                    {!turno.id_modelo ? (
                      <span className="cfg-linhas-hint" style={{ color: "#d97706" }}>
                        Salve o turno primeiro para poder vincular a outras linhas.
                      </span>
                    ) : (
                      <>
                        <div className="cfg-linhas-checks">
                          {linhas.map((l) => (
                            <label key={l.id} className="cfg-vincular-check">
                              <input
                                type="checkbox"
                                checked={linhasVinc.includes(l.id)}
                                onChange={() => toggleLinha(i, l.id)}
                              />
                              {l.nome}
                            </label>
                          ))}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                          <button
                            type="button"
                            className="cfg-save-btn"
                            style={{ padding: "6px 14px", fontSize: 12 }}
                            onClick={() => saveVincular(i, turno.id_modelo)}
                          >
                            Aplicar vínculo
                          </button>
                          {vinculMsg && <span className="cfg-saved-msg">{vinculMsg}</span>}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </React.Fragment>
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
  // mapa id_ihm -> tipo_maquina local (para edição inline)
  const [tiposMaquinas, setTiposMaquinas] = useState({});

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
      .then(([p, m]) => {
        setPecas(p);
        setMaquinas(m);
        // inicializa o mapa de tipos com o que veio do servidor
        const map = {};
        m.forEach(maq => { map[maq.id] = maq.tipo_maquina ?? ""; });
        setTiposMaquinas(map);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedLinha]);

  function handleTipoChange(id_ihm, valor) {
    setTiposMaquinas(prev => ({ ...prev, [id_ihm]: valor }));
  }

  async function handleTipoBlur(id_ihm, valor) {
    // salva silenciosamente ao sair do campo
    try {
      await fetch(`${API_BASE}/api/config/machines/${id_ihm}/tipo`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo: valor }),
      });
      // Atualiza também a lista de máquinas para refletir na seção de disponíveis
      setMaquinas(prev => prev.map(m => m.id === id_ihm ? { ...m, tipo_maquina: valor } : m));
    } catch { /* silencia */ }
  }

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
                  <div className="cfg-rota-tipo">
                    <input
                      className="cfg-rota-tipo-input"
                      placeholder="Tipo (ex: Pintura)"
                      value={tiposMaquinas[m.id_ihm] ?? ""}
                      onChange={e => handleTipoChange(m.id_ihm, e.target.value)}
                      onBlur={e => handleTipoBlur(m.id_ihm, e.target.value)}
                      title="Tipo da máquina — máquinas com o mesmo tipo são intercambiáveis"
                    />
                  </div>
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
                      {(tiposMaquinas[m.id] || m.tipo_maquina) && (
                        <span className="cfg-tipo-badge">{tiposMaquinas[m.id] || m.tipo_maquina}</span>
                      )}
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
  const [tab, setTab] = useState("controle");

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
          className={`cfg-tab${tab === "controle" ? " cfg-tab--active" : ""}`}
          onClick={() => setTab("controle")}
        >
          Controle de Turno
        </button>
        <button
          className={`cfg-tab${tab === "turnos" ? " cfg-tab--active" : ""}`}
          onClick={() => setTab("turnos")}
        >
          Configurar Turnos
        </button>
        <button
          className={`cfg-tab${tab === "pecas" ? " cfg-tab--active" : ""}`}
          onClick={() => setTab("pecas")}
        >
          Peças e Roteiros
        </button>
      </div>

      <div className="cfg-card">
        {tab === "controle" && <ControleTurno />}
        {tab === "turnos"   && <GestaoTurnos />}
        {tab === "pecas"    && <GestaoPecas />}
      </div>
    </div>
  );
}
