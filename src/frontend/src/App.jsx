import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import Overview from "./pages/Overview";
import LinhaDetalhe from "./pages/linhadetalhe";
import MaquinaDetalhe from "./pages/MaquinaDetalhe";
import Configuracoes from "./pages/Configuracoes";

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/linha/:lineId" element={<LinhaDetalhe />} />
          <Route path="/maquina/:machineId" element={<MaquinaDetalhe />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}