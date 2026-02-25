import "./topbar.css";

export default function Topbar({ title, oeeGlobal, maquinasAtivas, maquinasTotal, dateTimeText, userInitials }) {
  return (
    <header className="topbar">
      <div className="tb-left">
        <h1 className="tb-title">{title}</h1>

        <div className="tb-kpis">
          <span className="tb-dot ok" />
          <span className="tb-kpi">
            <span className="tb-kpi-label">OEE Global:</span>
            <strong>{oeeGlobal}%</strong>
          </span>

          <span className="tb-sep">•</span>

          <span className="tb-kpi">
            <span className="tb-kpi-label">Máquinas Ativas:</span>
            <strong>{maquinasAtivas}/{maquinasTotal}</strong>
          </span>
        </div>
      </div>

      <div className="tb-right">
        <div className="tb-pill">{dateTimeText}</div>
        <div className="tb-avatar" title="Usuário">
          {userInitials}
        </div>
      </div>
    </header>
  );
}