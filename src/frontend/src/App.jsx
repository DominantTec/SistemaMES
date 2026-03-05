import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import Overview from "./pages/Overview";
import LinhaDetalhe from "./pages/linhadetalhe"

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/linha/:lineId" element={<LinhaDetalhe />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}