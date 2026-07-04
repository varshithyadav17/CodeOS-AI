import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Loader2, ArrowLeft, GitBranch, FileCode2, Network } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import SelectionBar from "../components/codeos/SelectionBar";
import ShortcutsOverlay from "../components/codeos/ShortcutsOverlay";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ErrorState } from "../components/ui/state";
import Skeleton, { SkeletonGrid } from "../components/ui/skeleton";
import { WorkspaceProvider, useWorkspace } from "../context/WorkspaceContext";

// Each workspace tab is its own chunk. Radix's Tabs.Content unmounts
// inactive tabs by default, so only one of these is ever live at a time —
// but a plain top-level import still ships all seven (plus reactflow,
// react-markdown, and the syntax highlighter they pull in) in the initial
// RepoDetail bundle regardless of which tab is open. Lazy-loading means a
// user who only ever uses Chat + Files never downloads the Knowledge
// Graph or Architecture panel code at all.
const KnowledgeGraph = lazy(() => import("../components/codeos/KnowledgeGraph"));
const ChatPanel = lazy(() => import("../components/codeos/ChatPanel"));
const ReviewPanel = lazy(() => import("../components/codeos/ReviewPanel"));
const ArchitecturePanel = lazy(() => import("../components/codeos/ArchitecturePanel"));
const TimelinePanel = lazy(() => import("../components/codeos/TimelinePanel"));
const DocsPanel = lazy(() => import("../components/codeos/DocsPanel"));
const FilesPanel = lazy(() => import("../components/codeos/FilesPanel"));

function PanelFallback() {
  return <SkeletonGrid cols={1} count={3} cardClassName="h-16" />;
}

const TAB_KEYS = ["chat", "review", "arch", "timeline", "docs", "graph", "files"];

/** Everything below this line is rendered inside the WorkspaceProvider and
 * can freely call useWorkspace(). Keeping it as a child component (rather
 * than inlining in RepoDetail) means the provider's `value` only needs to
 * be created once data is ready, and every panel shares that single
 * instance instead of re-deriving its own selection state. */
function Workspace({ repo }) {
  const { activeTab, setActiveTab, graph, selectFile, selectNode, clearSelection } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showShortcuts, setShowShortcuts] = useState(false);
  const appliedDeepLink = useRef(false);

  // One-time deep link: Memory page's "Open in workspace" navigates to
  // /repositories/{id}?file=...&symbol=... — apply it once graph/files are
  // loaded (i.e. once this component mounts, since it only mounts when
  // ready), then strip the params so it doesn't re-fire on re-renders.
  useEffect(() => {
    if (appliedDeepLink.current) return;
    const file = searchParams.get("file");
    const symbol = searchParams.get("symbol");
    if (!file && !symbol) return;
    appliedDeepLink.current = true;
    if (symbol) {
      const match = graph.nodes.find((n) => n.qualified_name === symbol);
      if (match) selectNode(match.id);
      else if (file) selectFile(file);
    } else if (file) {
      selectFile(file);
    }
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keyboard shortcuts: 1-7 to jump tabs, Esc to clear selection, ?/Shift+/
  // opens the shortcuts overlay. Skipped while the user is typing anywhere
  // (input/textarea/contenteditable) so it never steals a keystroke from
  // Chat, search boxes, etc.
  useEffect(() => {
    const handler = (e) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable;
      if (typing) return;
      if (e.key === "Escape") { setShowShortcuts(false); clearSelection(); return; }
      if (e.key === "?") { setShowShortcuts((s) => !s); return; }
      const idx = Number(e.key) - 1;
      if (idx >= 0 && idx < TAB_KEYS.length && !e.metaKey && !e.ctrlKey) {
        setActiveTab(TAB_KEYS[idx]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setActiveTab, clearSelection]);

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
      <div className="flex items-center gap-2">
        <TabsList className="glass-panel border border-white/10 rounded-xl h-9 p-1">
          <TabsTrigger value="chat" data-testid="tab-chat" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">AI Chat</TabsTrigger>
          <TabsTrigger value="review" data-testid="tab-review" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Code Review</TabsTrigger>
          <TabsTrigger value="arch" data-testid="tab-arch" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Architecture</TabsTrigger>
          <TabsTrigger value="timeline" data-testid="tab-timeline" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Timeline</TabsTrigger>
          <TabsTrigger value="docs" data-testid="tab-docs" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Docs</TabsTrigger>
          <TabsTrigger value="graph" data-testid="tab-graph" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Knowledge Graph</TabsTrigger>
          <TabsTrigger value="files" data-testid="tab-files" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Files</TabsTrigger>
        </TabsList>
        <button
          data-testid="shortcuts-trigger"
          onClick={() => setShowShortcuts(true)}
          aria-label="Show keyboard shortcuts"
          title="Keyboard shortcuts (?)"
          className="w-9 h-9 flex items-center justify-center text-xs mono text-white/40 hover:text-white border border-white/10 hover:border-white/30 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
        >
          ?
        </button>
      </div>

      <div className="mt-3"><SelectionBar /></div>

      <TabsContent value="chat" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="ChatPanel"><Suspense fallback={<PanelFallback />}><ChatPanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="review" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="ReviewPanel"><Suspense fallback={<PanelFallback />}><ReviewPanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="arch" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="ArchitecturePanel"><Suspense fallback={<PanelFallback />}><ArchitecturePanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="timeline" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="TimelinePanel"><Suspense fallback={<PanelFallback />}><TimelinePanel repoId={repo.id} /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="docs" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="DocsPanel"><Suspense fallback={<PanelFallback />}><DocsPanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="graph" className="mt-4 space-y-3 animate-in fade-in duration-150">
        <div className="flex flex-wrap items-center gap-3 text-[11px] mono">
          {[
            { l: "file", c: "#D500F9" }, { l: "class", c: "#2979FF" },
            { l: "function", c: "#FF9100" }, { l: "method", c: "#FF9100" },
          ].map((x) => (
            <span key={x.l} className="flex items-center gap-1.5 text-white/60"><span className="w-2 h-2 rounded-full" style={{ background: x.c }} aria-hidden="true" />{x.l}</span>
          ))}
          <span className="text-white/30">· showing top {graph.nodes.length} nodes · click a node to select it everywhere</span>
        </div>
        <ErrorBoundary label="KnowledgeGraph"><Suspense fallback={<PanelFallback />}><KnowledgeGraph nodes={graph.nodes} edges={graph.edges} /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="files" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="FilesPanel"><Suspense fallback={<PanelFallback />}><FilesPanel /></Suspense></ErrorBoundary>
      </TabsContent>

      {showShortcuts && <ShortcutsOverlay onClose={() => setShowShortcuts(false)} />}
    </Tabs>
  );
}

export default function RepoDetail() {
  const { id } = useParams();
  const [repo, setRepo] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const refresh = useCallback(async () => {
    const r = await api.get(`/repos/${id}`);
    setRepo(r.data);
    if (r.data.status === "ready") {
      const [g, f] = await Promise.all([
        api.get(`/repos/${id}/graph?limit=120`),
        api.get(`/repos/${id}/files`),
      ]);
      setGraph(g.data);
      setFiles(f.data);
    }
  }, [id]);

  // Lightweight poll used while ingestion is in progress — hits the
  // purpose-built /status endpoint instead of re-fetching the full repo
  // document every 2.5s. Once it flips to "ready" (or "failed"), we do one
  // full refresh() to pull in stats/graph/files.
  const pollStatus = useCallback(async () => {
    try {
      const r = await api.get(`/repos/${id}/status`);
      setRepo((prev) => (prev ? { ...prev, ...r.data } : prev));
      if (["ready", "failed"].includes(r.data.status)) {
        await refresh();
      }
    } catch {
      // Transient network hiccups during polling shouldn't interrupt the
      // view — the next tick retries automatically.
    }
  }, [id, refresh]);

  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    refresh().catch((e) => setLoadError(e?.response?.data?.detail || "Failed to load repository")).finally(() => setLoading(false));
  }, [refresh, retryNonce]);

  // Poll while not ready. Depends on `repo?.status` rather than `repo`
  // itself on purpose: `repo` gets a new object identity on every poll
  // tick (see setRepo above), so depending on the whole object would tear
  // down and recreate the interval every 2.5s for no reason — the interval
  // only needs to restart when the status actually transitions.
  useEffect(() => {
    if (!repo) return;
    if (["ready", "failed"].includes(repo.status)) return;
    const t = setInterval(pollStatus, 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo?.status, pollStatus]);

  if (loading || (!repo && !loadError)) {
    return (
      <div className="p-6 md:p-8 space-y-5" data-testid="repo-detail-loading">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-8 w-72" />
        <SkeletonGrid cols={5} count={5} cardClassName="h-16" />
        <Skeleton className="h-9 w-full max-w-xl" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-10" data-testid="repo-detail-error">
        <ErrorState message={loadError} onRetry={() => setRetryNonce((n) => n + 1)} />
      </div>
    );
  }

  const ready = repo.status === "ready";

  return (
    <div className="p-6 md:p-8 space-y-5" data-testid="repo-detail-root">
      <div>
        <Link to="/repositories" className="text-xs text-white/40 hover:text-white inline-flex items-center gap-1.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm transition-colors duration-150"><ArrowLeft size={12} aria-hidden="true" /> All repositories</Link>
        <div className="flex flex-wrap items-end justify-between mt-2 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// "}{repo.source}</div>
            <h1 className="text-3xl font-semibold tracking-tighter mt-0.5" style={{ fontFamily: "Chivo" }} data-testid="repo-name">{repo.name}</h1>
            {repo.source_url && <div className="text-[11px] mono text-white/40 mt-1">{repo.source_url}</div>}
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className={`mono uppercase tracking-[0.18em] text-[10px] px-2 py-1 rounded-sm border ${ready ? "border-[#34C759]/40 text-[#34C759]" : repo.status === "failed" ? "border-[#FF3B30]/40 text-[#FF3B30]" : "border-[#FFB300]/40 text-[#FFB300]"}`} data-testid="repo-status">{repo.status}</span>
            {repo.branch && <span className="mono text-white/40 flex items-center gap-1"><GitBranch size={11} aria-hidden="true" />{repo.branch}</span>}
          </div>
        </div>
      </div>

      {!ready && (
        <div className="glass-panel border border-white/10 rounded-xl p-5" role="status" aria-live="polite">
          <div className="text-xs text-white/60 mb-2 flex items-center gap-2"><Loader2 size={12} className="animate-spin text-[#3FC8E8]" aria-hidden="true" /> {repo.message || "Processing…"}</div>
          <div className="h-1.5 bg-white/5 rounded-sm overflow-hidden">
            <div className="h-full bg-[#3FC8E8] transition-all duration-500" style={{ width: `${repo.progress || 0}%` }} />
          </div>
          {repo.status === "failed" && (
            <p className="text-xs text-[#FF3B30] mt-3" data-testid="ingestion-error" role="alert">{repo.message || "Ingestion failed."}</p>
          )}
        </div>
      )}

      {ready && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 animate-in fade-in duration-200">
            {[
              { l: "Files", v: repo.stats.files, i: FileCode2 },
              { l: "LOC", v: repo.stats.loc, i: FileCode2 },
              { l: "Nodes", v: repo.stats.nodes, i: Network },
              { l: "Edges", v: repo.stats.edges, i: Network },
              { l: "Chunks", v: repo.stats.chunks, i: FileCode2 },
            ].map((s) => (
              <div key={s.l} className="glass-panel border border-white/10 rounded-xl p-3 hover:border-white/20 transition-colors duration-150" data-testid={`repo-stat-${s.l.toLowerCase()}`}>
                <div className="text-[10px] uppercase tracking-[0.18em] mono text-white/40 flex items-center gap-1.5"><s.i size={11} aria-hidden="true" /> {s.l}</div>
                <div className="text-2xl font-semibold tracking-tighter mt-1" style={{ fontFamily: "Chivo" }}>{s.v}</div>
              </div>
            ))}
          </div>

          <WorkspaceProvider repoId={repo.id} repo={repo} graph={graph} files={files}>
            <Workspace repo={repo} />
          </WorkspaceProvider>
        </>
      )}
    </div>
  );
}
