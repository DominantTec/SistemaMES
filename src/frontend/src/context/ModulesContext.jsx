import { createContext, useContext, useEffect, useState } from "react";

const DEFAULT_API = `http://${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API;

const ModulesContext = createContext(new Set(["base"]));

export function ModulesProvider({ children }) {
  const [modules, setModules] = useState(new Set(["base"]));

  useEffect(() => {
    fetch(`${API_BASE}/api/modules`)
      .then((r) => r.json())
      .then((list) => setModules(new Set(list)))
      .catch(() => {});
  }, []);

  return (
    <ModulesContext.Provider value={modules}>
      {children}
    </ModulesContext.Provider>
  );
}

export function useModules() {
  return useContext(ModulesContext);
}

export function useModule(name) {
  return useContext(ModulesContext).has(name);
}
