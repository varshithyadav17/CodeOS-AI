import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useState } from "react";
import { toast } from "sonner";
import FolderGit2Icon from "../assets/icons/folder-git-2.svg?react";
import LogOutIcon from "../assets/icons/log-out.svg?react";
import DashboardIcon from "../assets/icons/layout-dashboard.svg?react";
import BrainIcon from "../assets/icons/brain.svg?react";
import logoLight from "../assets/logo/logo-light.svg";

const NavItem = ({ to, icon: Icon, label, testId }) => (
  <NavLink
    to={to}
    aria-label={label}
    data-testid={testId}
    className={({ isActive }) =>
      `flex items-center gap-3 mx-2 px-3.5 py-2.5 text-sm rounded-lg transition-all duration-200 border-l-2 ${
        isActive
          ? "bg-white/10 text-white border-[#3FC8E8] shadow-[0_0_0_1px_rgba(255,255,255,0.06)_inset]"
          : "text-white/60 hover:text-white hover:bg-white/[0.06] border-transparent"
      }`
    }
  >
    <Icon width={16} height={16} />
    <span className="hidden md:inline">{label}</span>
  </NavLink>
);

export default function Sidebar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [signingOut, setSigningOut] = useState(false);
  const onLogout = async () => {
    setSigningOut(true);
    try { await logout(); nav("/login"); }
    catch { toast.error("Sign out failed. Your session is still active. Please try again."); }
    finally { setSigningOut(false); }
  };

  return (
    <aside className="w-16 md:w-60 shrink-0 glass-panel rounded-none border-y-0 border-l-0 flex flex-col relative z-10" data-testid="sidebar">
      <div className="px-2 md:px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <img src={logoLight} alt="CodeOS AI" className="h-6 w-full object-contain md:w-auto" />
        </div>
        <div className="hidden md:block text-[10px] text-white/40 mono uppercase tracking-widest mt-1.5">AI for Software</div>
      </div>

      <nav className="flex-1 py-4">
        <div className="hidden md:block px-4 mb-2 text-[10px] uppercase tracking-[0.18em] text-white/30 mono">Workspace</div>
        <div className="space-y-0.5">
          <NavItem to="/dashboard" icon={DashboardIcon} label="Dashboard" testId="nav-dashboard" />
          <NavItem to="/repositories" icon={FolderGit2Icon} label="Repositories" testId="nav-repositories" />
          <NavItem to="/memory" icon={BrainIcon} label="Engineering Memory" testId="nav-memory" />
        </div>
      </nav>

      <div className="px-4 py-3 border-t border-white/10 text-xs">
        <div className="hidden md:flex items-center gap-2 mb-3 text-white/70">
          <div className="w-6 h-6 rounded-md bg-white/10 flex items-center justify-center text-[10px] border border-white/10">
            {(user?.name || user?.email || "U").slice(0, 1).toUpperCase()}
          </div>
          <div className="truncate" data-testid="user-email">{user?.email}</div>
        </div>
        <button
          data-testid="logout-button"
          aria-label="Sign out"
          onClick={onLogout}
          disabled={signingOut}
          className="w-full flex items-center justify-center gap-2 py-2 border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] hover:border-white/25 text-white/70 hover:text-white transition-all duration-200 rounded-lg"
        >
          <LogOutIcon width={12} height={12} /> <span className="hidden md:inline">Sign out</span>
        </button>
      </div>
    </aside>
  );
}
