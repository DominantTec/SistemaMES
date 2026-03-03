import "./sidebar.css";

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sb-header">
        <div className="sb-logo">📈</div>
        <div className="sb-title">PCP Monitor</div>
      </div>

      <nav className="sb-nav">
        <button className="sb-item active" type="button">
          <span className="sb-ico">▦</span>
          <span>Visão Geral</span>
        </button>

        <button className="sb-item" type="button">
          <span className="sb-ico">≡</span>
          <span>Ordens em Aberto</span>
        </button>
      </nav>

      <div className="sb-section">
        <div className="sb-section-title">LINHAS DE PRODUÇÃO</div>

        <button className="sb-line" type="button"><span className="dot"></span> Linha 505</button>
        <button className="sb-line" type="button"><span className="dot"></span> Linha 504</button>
        <button className="sb-line" type="button"><span className="dot"></span> Linha 506</button>
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