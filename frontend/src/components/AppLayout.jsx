import { Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import CpuIcon from "../assets/icons/cpu.svg?react";
import Sidebar from "./Sidebar";

export default function AppLayout() {
  const { user } = useAuth();

  return (
    <div className="h-screen overflow-hidden flex text-white relative">
      <div className="app-background" aria-hidden="true" />
      <Sidebar />

      <main className="flex-1 min-w-0 overflow-auto relative z-10">
        <div className="glass-panel-soft rounded-none border-x-0 border-t-0 sticky top-0 z-20 h-12 flex items-center px-6 text-xs text-white/40 mono">
          <CpuIcon width={12} height={12} className="mr-2" />
          <span className="truncate">codeos-ai // {user?.email}</span>
          <span className="hidden md:inline ml-auto text-white/30">v1.0.0</span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
