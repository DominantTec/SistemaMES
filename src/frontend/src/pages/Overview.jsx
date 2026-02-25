import { useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar/Topbar";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

export default function Overview() {
  const [topbar, setTopbar] = useState(null);
  const [topbarError, setTopbarError] = useState(null);

  const [lines, setLines] = useState([]);
  const [linesError, setLinesError] = useState(null);

  const [machinesByLine, setMachinesByLine] = useState({});
  const [machinesError, setMachinesError] = useState(null);

  // machineLive[machineId] = último ponto da timeline (linha do pivot)
  const [machineLive, setMachineLive] = useState({});
  const machineSocketsRef = useRef({}); // { [machineId]: WebSocket }
  const machineRetryRef = useRef({}); // { [machineId]: retryCount }
  const machineRetryTimersRef = useRef({}); // { [machineId]: timer }

  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const retryTimerRef = useRef(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;

    console.log("API_BASE:", API_BASE);

    // ===== Topbar (HTTP inicial) =====
    fetch(`${API_BASE}/api/dashboard/topbar`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`Topbar HTTP ${r.status}`);
        return r.json();
      })
      .then(setTopbar)
      .catch((e) => setTopbarError(String(e)));

    // ===== Linhas + máquinas =====
    (async () => {
      try {
        setLinesError(null);
        setMachinesError(null);

        const r = await fetch(`${API_BASE}/api/lines`);
        if (!r.ok) throw new Error(`Lines HTTP ${r.status}`);
        const data = await r.json();

        if (!Array.isArray(data)) {
          throw new Error(`Lines não é array. Veio: ${JSON.stringify(data)}`);
        }

        setLines(data);

        const results = await Promise.all(
          data.map(async (l) => {
            const mr = await fetch(`${API_BASE}/api/lines/${l.id}/machines`);
            if (!mr.ok) throw new Error(`Machines HTTP ${mr.status} (line ${l.id})`);
            const machines = await mr.json();
            return [l.id, machines];
          })
        );

        const map = {};
        for (const [lineId, machines] of results) map[lineId] = machines || [];
        setMachinesByLine(map);

        // ===== WebSocket por máquina (timeline) =====
        const wsBase = API_BASE.replace(/^http/, "ws");

        const allMachines = results.flatMap(([_, machines]) => machines || []);

        const connectMachineWs = (machineId) => {
          if (!aliveRef.current) return;
          if (machineSocketsRef.current[machineId]) return;

          const url = `${wsBase}/ws/machines/${machineId}/timeline`;
          console.log("WS Machine URL:", url);

          const ws = new WebSocket(url);
          machineSocketsRef.current[machineId] = ws;

          ws.onopen = () => {
            machineRetryRef.current[machineId] = 0;
          };

          ws.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data);

              if (msg.type === "machine_timeline") {
                const rows = Array.isArray(msg.data) ? msg.data : [];
                const last = rows.length ? rows[rows.length - 1] : null;

                if (last) {
                  setMachineLive((prev) => ({
                    ...prev,
                    [machineId]: last,
                  }));
                }
              }
            } catch (err) {
              console.warn("WS machine parse error:", machineId, err);
            }
          };

          ws.onclose = () => {
            delete machineSocketsRef.current[machineId];
            if (!aliveRef.current) return;

            const prevRetry = machineRetryRef.current[machineId] || 0;
            const nextRetry = prevRetry + 1;
            machineRetryRef.current[machineId] = nextRetry;

            const delay = Math.min(1000 * 2 ** (nextRetry - 1), 10000);
            machineRetryTimersRef.current[machineId] = setTimeout(() => {
              connectMachineWs(machineId);
            }, delay);
          };
        };

        for (const m of allMachines) {
          if (!m?.id) continue;
          connectMachineWs(m.id);
        }
      } catch (e) {
        console.error(e);
        setLinesError(String(e));
      }
    })();

    // ===== WebSocket (Topbar) =====
    const wsBase = API_BASE.replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/dashboard`;

    const connect = () => {
      if (!aliveRef.current) return;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "topbar") setTopbar(msg.data);
        } catch (err) {
          console.warn("WS parse error:", err);
        }
      };

      ws.onclose = () => {
        if (!aliveRef.current) return;
        retryRef.current += 1;
        const delay = Math.min(1000 * 2 ** (retryRef.current - 1), 10000);
        retryTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      aliveRef.current = false;

      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (wsRef.current) wsRef.current.close();

      for (const machineIdStr of Object.keys(machineRetryTimersRef.current)) {
        const t = machineRetryTimersRef.current[machineIdStr];
        if (t) clearTimeout(t);
      }
      machineRetryTimersRef.current = {};

      for (const machineIdStr of Object.keys(machineSocketsRef.current)) {
        try {
          machineSocketsRef.current[machineIdStr]?.close();
        } catch {}
      }
      machineSocketsRef.current = {};
    };
  }, []);

  if (topbarError) return <div style={{ color: "crimson" }}>Erro Topbar: {topbarError}</div>;
  if (!topbar) return <div>Carregando Topbar...</div>;

  // ===== helpers =====
  const fmt = (v) => {
    if (v === null || v === undefined || v === "") return "-";
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
    return String(v);
  };

  const statusColor = (statusText) => {
    if (!statusText) return "#6b7280";
    const s = String(statusText).toLowerCase();
    if (s.includes("produz")) return "#16a34a";
    if (s.includes("parad")) return "#dc2626";
    if (s.includes("manuten")) return "#f59e0b";
    if (s.includes("limpez")) return "#3b82f6";
    return "#6b7280";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Topbar {...topbar} />

      {linesError && <div style={{ color: "crimson" }}>Erro Linhas/Máquinas: {linesError}</div>}
      {machinesError && <div style={{ color: "crimson" }}>Erro Máquinas: {machinesError}</div>}

      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {lines.length === 0 ? (
          <div style={{ color: "#6b7280" }}>Nenhuma linha carregada.</div>
        ) : (
          lines.map((line) => (
            <div
              key={line.id}
              style={{
                background: "#fff",
                border: "1px solid #eee",
                borderRadius: 12,
                padding: 14,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <span
                  style={{
                    background: "#2563eb",
                    color: "#fff",
                    fontWeight: 700,
                    padding: "6px 10px",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                >
                  {line.name}
                </span>

                <span style={{ color: "#6b7280", fontSize: 13 }}>
                  Máquinas: {(machinesByLine[line.id] || []).length}
                </span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                  gap: 12,
                }}
              >
                {(machinesByLine[line.id] || []).map((m) => {
                  const live = machineLive[m.id];
                  const status = live?.status_maquina; // vem mapeado no backend (texto)
                  const barColor = statusColor(status);

                  // campos que existem no seu tb_registrador
                  const produzido = live?.produzido;
                  const totalProduzido = live?.total_produzido;
                  const reprovado = live?.reprovado;
                  const meta = live?.meta;
                  const motivoParada = live?.motivo_parada;

                  return (
                    <div
                      key={m.id}
                      style={{
                        border: "1px solid #e5e7eb",
                        borderRadius: 12,
                        background: "#f9fafb",
                        overflow: "hidden",
                        display: "flex",
                        flexDirection: "column",
                        minHeight: 150,
                      }}
                    >
                      {/* faixa superior (status) */}
                      <div style={{ height: 10, background: barColor }} />

                      <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                          <div style={{ fontWeight: 800, color: "#111827" }}>{m.name}</div>
                          <div style={{ fontSize: 12, color: "#6b7280" }}>ID {m.id}</div>
                        </div>

                        <div style={{ fontSize: 12, color: "#111827" }}>
                          <span style={{ fontWeight: 700 }}>Status:</span>{" "}
                          <span style={{ color: barColor, fontWeight: 800 }}>{fmt(status)}</span>
                        </div>

                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "1fr 1fr",
                            gap: 8,
                          }}
                        >
                          <div
                            style={{
                              border: "1px solid #e5e7eb",
                              borderRadius: 10,
                              padding: 10,
                              background: "#fff",
                            }}
                          >
                            <div style={{ fontSize: 11, color: "#6b7280" }}>Produzido</div>
                            <div style={{ fontWeight: 800, color: "#111827" }}>{fmt(produzido)}</div>
                          </div>

                          <div
                            style={{
                              border: "1px solid #e5e7eb",
                              borderRadius: 10,
                              padding: 10,
                              background: "#fff",
                            }}
                          >
                            <div style={{ fontSize: 11, color: "#6b7280" }}>Reprovado</div>
                            <div style={{ fontWeight: 800, color: "#111827" }}>{fmt(reprovado)}</div>
                          </div>

                          <div
                            style={{
                              border: "1px solid #e5e7eb",
                              borderRadius: 10,
                              padding: 10,
                              background: "#fff",
                            }}
                          >
                            <div style={{ fontSize: 11, color: "#6b7280" }}>Total produzido</div>
                            <div style={{ fontWeight: 800, color: "#111827" }}>{fmt(totalProduzido)}</div>
                          </div>

                          <div
                            style={{
                              border: "1px solid #e5e7eb",
                              borderRadius: 10,
                              padding: 10,
                              background: "#fff",
                            }}
                          >
                            <div style={{ fontSize: 11, color: "#6b7280" }}>Meta</div>
                            <div style={{ fontWeight: 800, color: "#111827" }}>{fmt(meta)}</div>
                          </div>
                        </div>

                        {/* motivo parada só faz sentido se não estiver produzindo */}
                        <div style={{ fontSize: 11, color: "#6b7280" }}>
                          Motivo parada: <span style={{ color: "#111827", fontWeight: 700 }}>{fmt(motivoParada)}</span>
                        </div>

                        <div style={{ marginTop: 2, fontSize: 11, color: "#6b7280" }}>
                          Última atualização: {fmt(live?.dt_created_at)}
                        </div>

                        {/* Debug (se quiser, descomente para ver tudo que veio do backend) */}
                        {/* <pre style={{ fontSize: 10, color: "#111827", whiteSpace: "pre-wrap" }}>
                          {live ? JSON.stringify(live, null, 2) : "SEM DADOS"}
                        </pre> */}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}