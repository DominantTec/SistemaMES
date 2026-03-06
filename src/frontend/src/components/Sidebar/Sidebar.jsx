import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

export default function Sidebar() {
  const [linhas, setLinhas] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/lines`)
      .then((r) => r.json())
      .then(setLinhas)
      .catch(() => {});
  }, []);

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

        <button className="sb-item" type="button">
          <span className="sb-ico">≡</span>
          <span>Ordens em Aberto</span>
        </button>
      </nav>

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
        <div className="sb-card-title">Turno Atual: <strong>T2</strong></div>
        <div className="sb-card-sub">Encerra em 04:32h</div>
        <div className="progress">
          <div className="progress-bar" style={{ width: "68%" }} />
        </div>
      </div>
    </aside>
  );
}