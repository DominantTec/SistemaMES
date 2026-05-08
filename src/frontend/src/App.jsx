import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ModulesProvider } from "./context/ModulesContext";
import { useModule } from "./context/ModulesContext";
import AppLayout from "./layouts/AppLayout";
import Overview from "./pages/Overview";
import LinhaDetalhe from "./pages/linhadetalhe";
import MaquinaDetalhe from "./pages/MaquinaDetalhe";
import Configuracoes from "./pages/Configuracoes";
import Painel from "./pages/Painel";
import PainelMES from "./pages/PainelMES";
import PainelTV from "./pages/PainelTV";
import Historico from "./pages/Historico";
import OrdensProducao from "./pages/OrdensProducao";
import Alertas from "./pages/Alertas";
import Manutencao from "./pages/Manutencao";

function AppRoutes() {
  const hasOp      = useModule("op");
  const hasAlertas = useModule("alertas");
  const hasOs      = useModule("os");

  return (
    <Routes>
      {/* Painéis TV — sem sidebar, tela cheia */}
      <Route path="/painel-tv"  element={<PainelTV />} />
      <Route path="/painel"     element={<Painel />} />
      <Route path="/painel-mes" element={<PainelMES />} />

      {/* Rotas normais com sidebar */}
      <Route path="/*" element={
        <AppLayout>
          <Routes>
            <Route path="/"                    element={<Overview />} />
            <Route path="/linha/:lineId"        element={<LinhaDetalhe />} />
            <Route path="/maquina/:machineId"   element={<MaquinaDetalhe />} />
            <Route path="/configuracoes"        element={<Configuracoes />} />
            <Route path="/historico"            element={<Historico />} />
            {hasOp      && <Route path="/ordens"     element={<OrdensProducao />} />}
            {hasAlertas && <Route path="/alertas"    element={<Alertas />} />}
            {hasOs      && <Route path="/manutencao" element={<Manutencao />} />}
          </Routes>
        </AppLayout>
      } />
    </Routes>
  );
}

export default function App() {
  return (
    <ModulesProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ModulesProvider>
  );
}
