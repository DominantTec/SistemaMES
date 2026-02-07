BASE_CSS = """
<style>
/* ---- Topbar ---- */
.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  padding: 10px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  background: #FFFFFF;
}
.topbar-left{
  display:flex;
  align-items:baseline;
  gap:12px;
  flex-wrap:wrap;
}
.topbar-title{
  font-size: 22px;
  font-weight: 800;
  color:#111827;
  margin:0;
}
.topbar-divider{
  width:1px;
  height:20px;
  background:#E5E7EB;
}
.kpi{
  display:flex;
  align-items:center;
  gap:8px;
  color:#374151;
  font-size: 14px;
}
.kpi b{
  color:#111827;
  font-size: 15px;
}
.topbar-right{
  display:flex;
  align-items:center;
  gap:10px;
}
.time-pill{
  padding: 8px 10px;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  background:#F9FAFB;
  font-weight: 700;
  color:#111827;
  font-size: 13px;
}

/* ---- Eventos ---- */
.events-row{
  margin-top: 10px;
  padding: 10px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  background: #FFFFFF;
  display:flex;
  gap:12px;
  align-items:center;
  overflow:hidden;
}
.events-label{
  font-weight:800;
  color:#111827;
  white-space:nowrap;
}
.event-item{
  display:flex;
  align-items:center;
  gap:10px;
  padding: 0 10px;
  border-left: 1px solid #333232;
  white-space:nowrap;
  color:#374151;
  font-size: 14px;
}
.event-time{
  color:#6B7280;
  font-variant-numeric: tabular-nums;
}
.event-maq{
  font-weight:800;
  color:#111827;
}
.dot{
  width:10px;
  height:10px;
  border-radius:999px;
  display:inline-block;
}
.dot-ok{ background:#22C55E; }
.dot-warn{ background:#F59E0B; }
.dot-err{ background:#EF4444; }
.button-sidebar-pg-atual {
  display: flex;
  align-items: left;
  gap: 20px;

  padding: 12px 14px;
  border-radius: 12px;

  background: #FCD56D;
  color: #111827;

  font-weight: 800;
  font-size: 20px;

  width: 100%;
  border: none;
  box-shadow: none;

  cursor: pointer;
}
.button-sidebar {
  display: flex;
  align-items: left;
  gap: 20px;

  padding: 12px 14px;
  border-radius: 12px;

  background: transparent;
  color: #111827;

  font-weight: 800;
  font-size: 20px;

  width: 100%;
  border: none;
  box-shadow: none;

  cursor: pointer;
}
</style>
"""