import { Suspense, lazy, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../components/ui/tabs";
import SelectionBar from "./SelectionBar";
import WorkspaceHeader from "./WorkspaceHeader";
import LoadingOverlay from "./LoadingOverlay";
import { ErrorBoundary } from "../../components/ErrorBoundary";
import { ErrorState } from "../../components/EmptyState";
import { SkeletonGrid } from "../../components/Skeleton";
import { useWorkspace } from "../../context/WorkspaceContext";
import { hasParsedWorkspace } from "../../lib/repositoryStatus";

const KnowledgeGraph = lazy(() => import("./KnowledgeGraph"));
const ChatPanel = lazy(() => import("./ChatPanel"));
const ReviewPanel = lazy(() => import("./ReviewPanel"));
const ArchitecturePanel = lazy(() => import("./ArchitecturePanel"));
const DocumentationPanel = lazy(() => import("./DocumentationPanel"));
const FilesPanel = lazy(() => import("./FilesPanel"));
const TimelinePanel = lazy(() => import("./TimelinePanel"));

function PanelFallback() {
  return <SkeletonGrid cols={1} count={3} cardClassName="h-16" />;
}

const TAB_KEYS = ["chat", "review", "arch", "graph", "files", "docs", "timeline"];

function Workspace() {
  const { repo, graph, activeTab, setActiveTab, selectFile, selectNode, clearSelection } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const file = searchParams.get("file");
    const symbol = searchParams.get("symbol");
    if (!file && !symbol) return;
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

  // Keyboard shortcuts: 1-7 to jump tabs, Esc to clear selection.
  useEffect(() => {
    const handler = (e) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable;
      if (typing) return;
      if (e.key === "Escape") { clearSelection(); return; }
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
      <TabsList className="glass-panel border border-white/10 rounded-xl h-auto min-h-9 p-1 flex flex-wrap justify-start">
        <TabsTrigger value="chat" data-testid="tab-chat" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">AI Chat</TabsTrigger>
        <TabsTrigger value="review" data-testid="tab-review" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Code Review</TabsTrigger>
        <TabsTrigger value="arch" data-testid="tab-arch" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Architecture</TabsTrigger>
        <TabsTrigger value="graph" data-testid="tab-graph" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Knowledge Graph</TabsTrigger>
        <TabsTrigger value="files" data-testid="tab-files" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Files</TabsTrigger>
        <TabsTrigger value="docs" data-testid="tab-docs" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Documentation</TabsTrigger>
        <TabsTrigger value="timeline" data-testid="tab-timeline" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/60 rounded-sm transition-colors duration-150">Timeline</TabsTrigger>
      </TabsList>

      <div className="mt-3"><SelectionBar /></div>

      <TabsContent value="chat" className="mt-4 animate-in fade-in duration-150">
        {repo.status === "ready" ? <ErrorBoundary label="ChatPanel"><Suspense fallback={<PanelFallback />}><ChatPanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary> : <IndexingNotice />}
      </TabsContent>

      <TabsContent value="review" className="mt-4 animate-in fade-in duration-150">
        {repo.status === "ready" ? <ErrorBoundary label="ReviewPanel"><Suspense fallback={<PanelFallback />}><ReviewPanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary> : <IndexingNotice />}
      </TabsContent>

      <TabsContent value="arch" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="ArchitecturePanel"><Suspense fallback={<PanelFallback />}><ArchitecturePanel repoId={repo.id} repoReady /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="graph" className="mt-4 space-y-3 animate-in fade-in duration-150">
        <ErrorBoundary label="KnowledgeGraph"><Suspense fallback={<PanelFallback />}><KnowledgeGraph nodes={graph.nodes} edges={graph.edges} /></Suspense></ErrorBoundary>
      </TabsContent>

      <TabsContent value="files" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="FilesPanel"><Suspense fallback={<PanelFallback />}><FilesPanel /></Suspense></ErrorBoundary>
      </TabsContent>
      <TabsContent value="docs" className="mt-4 animate-in fade-in duration-150">
        {repo.status === "ready" ? <ErrorBoundary label="DocumentationPanel"><Suspense fallback={<PanelFallback />}><DocumentationPanel repoId={repo.id} /></Suspense></ErrorBoundary> : <IndexingNotice />}
      </TabsContent>
      <TabsContent value="timeline" className="mt-4 animate-in fade-in duration-150">
        <ErrorBoundary label="Timeline"><Suspense fallback={<PanelFallback />}><TimelinePanel key={repo.id} repoId={repo.id} /></Suspense></ErrorBoundary>
      </TabsContent>
    </Tabs>
  );
}

function IndexingNotice() {
  const { repo, setActiveTab } = useWorkspace();
  return <div className="rounded-xl border border-cyan-300/20 bg-cyan-300/5 p-6" data-testid="ai-indexing-notice" role="status">
    <h2 className="font-medium text-cyan-100">Your code is parsed. AI search is still indexing.</h2>
    <p className="mt-2 text-sm text-white/60">{repo.message} Completed {repo.stats.chunks} of {repo.stats.chunks_total} chunks.</p>
    <button onClick={() => setActiveTab("graph")} className="mt-4 text-sm text-cyan-300 underline">Explore the graph while you wait</button>
  </div>;
}

export default function RepoDetail() {
  const { id } = useParams();
  const { repo, repoLoading, repoLoadError, loadRepo, clearCurrentRepo, pollRepoStatus } = useWorkspace();

  useEffect(() => {
    loadRepo(id);
    return () => clearCurrentRepo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!repo) return;
    if (["ready", "failed", "delete_failed"].includes(repo.status)) return;
    const t = setInterval(() => pollRepoStatus(id), repo.status === "waiting_embeddings" ? 10000 : 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, repo?.status]);

  if (repoLoading || (!repo && !repoLoadError)) {
    return <LoadingOverlay />;
  }

  if (repoLoadError) {
    return (
      <div className="p-10" data-testid="repo-detail-error">
        <ErrorState message={repoLoadError} onRetry={() => loadRepo(id)} />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-5" data-testid="repo-detail-root">
      <WorkspaceHeader repo={repo} />
      {hasParsedWorkspace(repo) && <Workspace />}
    </div>
  );
}
