import Sidebar from "../components/Sidebar/Sidebar";

export default function AppLayout({ children }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <main style={{ flex: 1, minWidth: 0, padding: "18px 22px" }}>
        {children}
      </main>
    </div>
  );
}