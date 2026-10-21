import { Suspense, lazy, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import AppLayout from "./components/AppLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Route-level code splitting: each page becomes its own chunk instead of
// all being bundled into the single ~740KB main chunk. AuthPage stays
// eager since it's the first thing an unauthenticated user needs and is
// small; the rest are lazy so /dashboard doesn't pay for RepoDetail's
// (reactflow, react-markdown, syntax highlighting) weight and vice versa.
import AuthPage from "./pages/Login/Login";
const Repositories = lazy(() => import("./pages/Repositories"));
const RepoDetail = lazy(() => import("./pages/Repository"));
const MemoryPage = lazy(() => import("./pages/Memory"));

function PageFallback() {
  return <div className="min-h-[40vh] flex items-center justify-center text-white/40 text-sm" role="status" aria-live="polite">Loading…</div>;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-white/40 text-sm" role="status">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { init, loading } = useAuth();
  const location = useLocation();
  useEffect(() => {
    init();
    // `init` is stable across renders (useCallback with no deps), so it
    // never needs to be in this dependency array — it should only run once
    // on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && location.pathname !== "/login" && location.pathname !== "/auth/callback") {
    return <div className="min-h-screen flex items-center justify-center text-white/40 text-sm" role="status">Booting CodeOS AI…</div>;
  }

  return (
    <ErrorBoundary label="CodeOS AI" onReset={() => window.location.assign("/repositories")}>
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="/auth/callback" element={<Navigate to="/login" replace />} />
        <Route element={<Protected><AppLayout /></Protected>}>
          <Route path="/" element={<Navigate to="/repositories" replace />} />
          <Route path="/repositories" element={<ErrorBoundary label="Repositories"><Suspense fallback={<PageFallback />}><Repositories /></Suspense></ErrorBoundary>} />
          <Route path="/repositories/:id" element={<ErrorBoundary label="Repository workspace"><Suspense fallback={<PageFallback />}><RepoDetail /></Suspense></ErrorBoundary>} />
          <Route path="/memory" element={<ErrorBoundary label="Engineering Memory"><Suspense fallback={<PageFallback />}><MemoryPage /></Suspense></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/repositories" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
