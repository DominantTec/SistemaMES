import { NavLink, useNavigate } from "react-router-dom";
import "./Sidebar.css";

const LINHAS = [
  { id: 1, nome: "Linha 505" },
  { id: 2, nome: "Linha 504" },
  { id: 3, nome: "Linha 506" },
];

export default function Sidebar() {
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
        {LINHAS.map((l) => (
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