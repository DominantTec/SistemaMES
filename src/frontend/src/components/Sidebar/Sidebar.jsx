import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

export default function Sidebar() {
  const [linhas,         setLinhas]         = useState([]);
  const [turno,          setTurno]          = useState(null);
  const [alertasBadge,   setAlertasBadge]   = useState(0);

  useEffect(() => {
    fetch(`${API_BASE}/api/lines`)
      .then((r) => r.json())
      .then(setLinhas)
      .catch(() => {});
  }, []);

  useEffect(() => {
    function fetchTurno() {
      fetch(`${API_BASE}/api/config/turno/atual`)
        .then((r) => r.json())
        .then(setTurno)
        .catch(() => {});
    }
    fetchTurno();
    const id = setInterval(fetchTurno, 30_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    function fetchAlertStats() {
      fetch(`${API_BASE}/api/alertas/stats`)
        .then((r) => r.json())
        .then((d) => setAlertasBadge(d.nao_reconhecidos ?? 0))
        .catch(() => {});
    }
    fetchAlertStats();
    const id = setInterval(fetchAlertStats, 15_000);
    return () => clearInterval(id);
  }, []);

  const emTurno        = turno && turno.nome !== "-";
  const aguardandoInicio = turno && turno.status === "aguardando_inicio";
  const progresso      = turno ? turno.progresso_pct : 0;
  const barColor       = aguardandoInicio ? "#f59e0b"
                       : progresso < 40   ? "#22c55e"
                       : progresso < 75   ? "#f59e0b"
                       : "#ef4444";

  return (
    <aside className="sidebar">
      <div className="sb-header">
        <div className="sb-logo">📈</div>
        <div className="sb-title">PCP Monitor</div>
      </div>

      <nav className="sb-nav">
        <NavLink
          to="/"
          end
          className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
        >
          <span className="sb-ico">▦</span>
          <span>Visão Geral</span>
        </NavLink>

        <NavLink
          to="/ordens"
          className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
        >
          <span className="sb-ico">≡</span>
          <span>Ordens de Produção</span>
        </NavLink>

        <NavLink
          to="/historico"
          className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
        >
          <span className="sb-ico">📊</span>
          <span>Histórico</span>
        </NavLink>

        <NavLink
          to="/alertas"
          className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
        >
          <span className="sb-ico">🔔</span>
          <span>Alertas</span>
          {alertasBadge > 0 && (
            <span className="sb-badge">{alertasBadge > 99 ? "99+" : alertasBadge}</span>
          )}
        </NavLink>

        <a
          href="/painel-tv"
          target="_blank"
          rel="noopener noreferrer"
          className="sb-item"
        >
          <span className="sb-ico">📺</span>
          <span>Painel TV</span>
        </a>
      </nav>

      <div className="sb-section">
        <div className="sb-section-title">GESTÃO</div>
        <NavLink
          to="/configuracoes"
          className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
        >
          <span className="sb-ico">⚙</span>
          <span>Configurações</span>
        </NavLink>
      </div>

      <div className="sb-section">
        <div className="sb-section-title">LINHAS DE PRODUÇÃO</div>
        {linhas.map((l) => (
          <NavLink
            key={l.id}
            to={`/linha/${l.id}`}
            className={({ isActive }) => "sb-line" + (isActive ? " active" : "")}
          >
            <span className="dot" />
            {l.nome}
          </NavLink>
        ))}
      </div>

      <div className="sb-spacer" />

      <div className="sb-card">
        {emTurno && !aguardandoInicio ? (
          <>
            <div className="sb-card-title">
              Turno Atual: <strong>{turno.nome}</strong>
            </div>
            <div className="sb-card-sub">Encerra em {turno.encerra_em}</div>
          </>
        ) : emTurno && aguardandoInicio ? (
          <>
            <div className="sb-card-title" style={{ color: "#f59e0b" }}>
              Aguardando início: <strong>{turno.nome}</strong>
            </div>
            <div className="sb-card-sub">Iniciar em Configurações → Turnos</div>
          </>
        ) : (
          <>
            <div className="sb-card-title">Turno Atual</div>
            <div className="sb-card-sub">Nenhum turno ativo</div>
          </>
        )}
        <div className="progress">
          <div className="progress-bar" style={{ width: `${progresso}%`, background: barColor }} />
        </div>
      </div>
    </aside>
  );
}
