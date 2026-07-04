import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";
import { LayoutDashboard, FolderGit2, LogOut, Cpu, Brain } from "lucide-react";
import logoLight from "../assets/logo-light.svg";

const NavItem = ({ to, icon: Icon, label, testId }) => (
  <NavLink
    to={to}
    data-testid={testId}
    className={({ isActive }) =>
      `flex items-center gap-3 mx-2 px-3.5 py-2.5 text-sm rounded-lg transition-all duration-200 border-l-2 ${
        isActive
          ? "bg-white/10 text-white border-[#3FC8E8] shadow-[0_0_0_1px_rgba(255,255,255,0.06)_inset]"
          : "text-white/60 hover:text-white hover:bg-white/[0.06] border-transparent"
      }`
    }
  >
    <Icon size={16} />
    <span>{label}</span>
  </NavLink>
);

export default function AppLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const onLogout = () => { logout(); nav("/login"); };

  return (
    <div className="min-h-screen flex text-white relative">
      <div className="app-background" aria-hidden="true" />
      <aside className="w-60 shrink-0 glass-panel rounded-none border-y-0 border-l-0 flex flex-col relative z-10" data-testid="sidebar">
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <img src={logoLight} alt="CodeOS AI" className="h-6 w-auto" />
          </div>
          <div className="text-[10px] text-white/40 mono uppercase tracking-widest mt-1.5">AI for Software</div>
        </div>

        <nav className="flex-1 py-4">
          <div className="px-4 mb-2 text-[10px] uppercase tracking-[0.18em] text-white/30 mono">Workspace</div>
          <div className="space-y-0.5">
            <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" testId="nav-dashboard" />
            <NavItem to="/repositories" icon={FolderGit2} label="Repositories" testId="nav-repositories" />
            <NavItem to="/memory" icon={Brain} label="Engineering Memory" testId="nav-memory" />
          </div>
        </nav>

        <div className="px-4 py-3 border-t border-white/10 text-xs">
          <div className="flex items-center gap-2 mb-3 text-white/70">
            <div className="w-6 h-6 rounded-md bg-white/10 flex items-center justify-center text-[10px] border border-white/10">
              {(user?.name || user?.email || "U").slice(0, 1).toUpperCase()}
            </div>
            <div className="truncate" data-testid="user-email">{user?.email}</div>
          </div>
          <button
            data-testid="logout-button"
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 py-2 border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] hover:border-white/25 text-white/70 hover:text-white transition-all duration-200 rounded-lg"
          >
            <LogOut size={12} /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto relative z-10">
        <div className="glass-panel-soft rounded-none border-x-0 border-t-0 sticky top-0 z-20 h-12 flex items-center px-6 text-xs text-white/40 mono">
          <Cpu size={12} className="mr-2" />
          <span>codeos-ai // {user?.email}</span>
          <span className="ml-auto text-white/30">v0.1.0</span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
