import Sidebar from "../components/Sidebar/Sidebar";

export default function AppLayout({ children }) {
  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <main style={{ flex: 1, minWidth: 0, marginLeft: 290, padding: "18px 22px" }}>
        {children}
      </main>
    </div>
  );
}