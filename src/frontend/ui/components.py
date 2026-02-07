from typing import List, Dict, Any

def dot_class(tipo: str) -> str:
    return {
        "ok": "dot-ok",
        "warn": "dot-warn",
        "err": "dot-err",
    }.get((tipo or "").lower(), "dot-warn")

def render_topbar(page_title: str, oee_global: float, maquinas_ativas: int, maquinas_total: int) -> str:
    return f"""
    <div class="topbar">
      <div class="topbar-left">
        <div class="topbar-title">{page_title}</div>
        <div class="topbar-divider"></div>
        <div class="kpi">
          <span class="dot dot-ok"></span>
          <span>OEE Global:</span>
          <b>{oee_global:.1f}%</b>
        </div>
        <div class="kpi">
          <span style="opacity:.65;">⚡</span>
          <span>Máquinas Ativas:</span>
          <b>{maquinas_ativas}/{maquinas_total}</b>
          </div>
      </div>

      <div class="topbar-right">
        <div style="width:34px; height:34px; border-radius:999px; background:#E5E7EB;"></div>
      </div>
    </div>
    """

def render_last_events(events: List[Dict[str, Any]]) -> str:
    e1, e2, e3, e4 = events

    return f"""
    <div class="events-row">
      <div class="events-label">ÚLTIMOS EVENTOS</div>

      <div class="event-item">
        <span class="event-time">{e1["hora"]}</span>
        <span class="dot {dot_class(e1.get("tipo"))}"></span>
        <span class="event-maq">{e1["maq"]}</span>
        <span class="event-msg">{e1["msg"]}</span>
      </div>

      <div class="event-item">
        <span class="event-time">{e2["hora"]}</span>
        <span class="dot {dot_class(e2.get("tipo"))}"></span>
        <span class="event-maq">{e2["maq"]}</span>
        <span class="event-msg">{e2["msg"]}</span>
      </div>

      <div class="event-item">
        <span class="event-time">{e3["hora"]}</span>
        <span class="dot {dot_class(e3.get("tipo"))}"></span>
        <span class="event-maq">{e3["maq"]}</span>
        <span class="event-msg">{e3["msg"]}</span>
      </div>
      
      <div class="event-item">
        <span class="event-time">{e4["hora"]}</span>
        <span class="dot {dot_class(e4.get("tipo"))}"></span>
        <span class="event-maq">{e4["maq"]}</span>
        <span class="event-msg">{e4["msg"]}</span>
      </div>
      
    </div>
    """