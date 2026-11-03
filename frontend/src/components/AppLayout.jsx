import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export default function AppLayout() {
  return (
    <div className="h-screen overflow-hidden flex text-white relative">
      <div className="app-background" aria-hidden="true" />
      <Sidebar />

      <main className="flex-1 min-w-0 overflow-auto relative z-10">
        <Outlet />
      </main>
    </div>
  );
}
