import { BrowserRouter, Routes, Route } from "react-router-dom";
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Painéis TV — sem sidebar, tela cheia */}
        <Route path="/painel-tv"  element={<PainelTV />} />
        <Route path="/painel"     element={<Painel />} />
        <Route path="/painel-mes" element={<PainelMES />} />

        {/* Rotas normais com sidebar */}
        <Route path="/*" element={
          <AppLayout>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/linha/:lineId" element={<LinhaDetalhe />} />
              <Route path="/maquina/:machineId" element={<MaquinaDetalhe />} />
              <Route path="/configuracoes" element={<Configuracoes />} />
              <Route path="/historico" element={<Historico />} />
              <Route path="/ordens" element={<OrdensProducao />} />
              <Route path="/alertas" element={<Alertas />} />
              <Route path="/manutencao" element={<Manutencao />} />
            </Routes>
          </AppLayout>
        } />
      </Routes>
    </BrowserRouter>
  );
}