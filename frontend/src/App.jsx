import { Suspense, lazy, useEffect } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./store/auth";
import AppLayout from "./layouts/AppLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { toast } from "sonner";

// Route-level code splitting: each page becomes its own chunk instead of
// all being bundled into the single ~740KB main chunk. AuthPage stays
// eager since it's the first thing an unauthenticated user needs and is
// small; the rest are lazy so /dashboard doesn't pay for RepoDetail's
// (reactflow, react-markdown, syntax highlighting) weight and vice versa.
import AuthPage from "./pages/AuthPage";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Repositories = lazy(() => import("./pages/Repositories"));
const RepoDetail = lazy(() => import("./pages/RepoDetail"));
const MemoryPage = lazy(() => import("./pages/MemoryPage"));

function PageFallback() {
  return <div className="min-h-[40vh] flex items-center justify-center text-white/40 text-sm" role="status" aria-live="polite">Loading…</div>;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-white/40 text-sm" role="status">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function GoogleCallback() {
  const navigate = useNavigate();
  const { googleExchange } = useAuth();
  useEffect(() => {
    const fragment = window.location.hash;
    const sid = new URLSearchParams(fragment.replace(/^#/, "?")).get("session_id");
    if (!sid) { navigate("/login"); return; }
    googleExchange(sid)
      .then(() => { toast.success("Signed in with Google"); navigate("/dashboard"); })
      .catch((e) => { toast.error(e?.response?.data?.detail || "Google sign-in failed"); navigate("/login"); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div className="min-h-screen flex items-center justify-center text-white/40 text-sm" role="status">Completing Google sign-in…</div>;
}

export default function App() {
  const { init, loading } = useAuth();
  const location = useLocation();
  useEffect(() => {
    init();
    // Zustand actions are referentially stable, so `init` never needs to be
    // in this dependency array — it should only run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && location.pathname !== "/login" && location.pathname !== "/auth/callback") {
    return <div className="min-h-screen flex items-center justify-center text-white/40 text-sm" role="status">Booting CodeOS AI…</div>;
  }

  return (
    <ErrorBoundary label="CodeOS AI" onReset={() => window.location.assign("/dashboard")}>
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="/auth/callback" element={<GoogleCallback />} />
        <Route element={<Protected><AppLayout /></Protected>}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ErrorBoundary label="Dashboard"><Suspense fallback={<PageFallback />}><Dashboard /></Suspense></ErrorBoundary>} />
          <Route path="/repositories" element={<ErrorBoundary label="Repositories"><Suspense fallback={<PageFallback />}><Repositories /></Suspense></ErrorBoundary>} />
          <Route path="/repositories/:id" element={<ErrorBoundary label="Repository workspace"><Suspense fallback={<PageFallback />}><RepoDetail /></Suspense></ErrorBoundary>} />
          <Route path="/memory" element={<ErrorBoundary label="Engineering Memory"><Suspense fallback={<PageFallback />}><MemoryPage /></Suspense></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
