// Registry de telas por TIPO de máquina (arquitetura schema-driven).
//
// Cada tipo de máquina pode ter sua própria forma de exibir os dados. A tela de
// detalhe (MaquinaDetalhe) mantém o cabeçalho comum e delega o CORPO ao componente
// registrado aqui conforme `tipo_maquina`. Se nenhum casar, usa-se a visão de
// produção padrão (OEE, paradas, Pareto etc.).
//
// Para adicionar um novo tipo: crie o componente e registre um matcher abaixo.
import EnsaioView from "./EnsaioView";
import FornoView from "./FornoView";

const REGISTRY = [
  {
    id: "ensaio",
    // tração / flexão / ensaio (sem acento e caixa)
    match: (tipo) => /trac|traç|flex|ensaio/i.test(tipo || ""),
    Component: EnsaioView,
  },
  {
    id: "forno",
    // forno mufla (tratamento térmico / perda ao fogo)
    match: (tipo) => /forno|mufla/i.test(tipo || ""),
    Component: FornoView,
  },
];

/** Retorna o componente de corpo para o tipo, ou null (usa produção padrão). */
export function getMachineView(tipo) {
  const found = REGISTRY.find((v) => v.match(tipo));
  return found ? found.Component : null;
}
