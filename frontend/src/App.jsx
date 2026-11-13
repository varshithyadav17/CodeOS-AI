import { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
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
const Dashboard = lazy(() => import("./pages/Dashboard"));
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
  const { user, authPending } = useAuth();
  const entry = user && !authPending ? <Navigate to="/dashboard" replace /> : <AuthPage />;

  return (
    <ErrorBoundary label="CodeOS AI" onReset={() => window.location.assign("/repositories")}>
      <Routes>
        <Route path="/" element={entry} />
        <Route path="/login" element={entry} />
        <Route path="/auth/callback" element={<Navigate to="/login" replace />} />
        <Route element={<Protected><AppLayout /></Protected>}>
          <Route path="/dashboard" element={<ErrorBoundary label="Dashboard"><Suspense fallback={<PageFallback />}><Dashboard /></Suspense></ErrorBoundary>} />
          <Route path="/repositories" element={<ErrorBoundary label="Repositories"><Suspense fallback={<PageFallback />}><Repositories /></Suspense></ErrorBoundary>} />
          <Route path="/repositories/:id" element={<ErrorBoundary label="Repository workspace"><Suspense fallback={<PageFallback />}><RepoDetail /></Suspense></ErrorBoundary>} />
          <Route path="/memory" element={<ErrorBoundary label="Engineering Memory"><Suspense fallback={<PageFallback />}><MemoryPage /></Suspense></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/repositories" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
