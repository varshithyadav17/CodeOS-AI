import { useEffect } from "react";
import { toast } from "sonner";
import { useWorkspace } from "../../context/WorkspaceContext";
import RepositoryUpload from "./RepositoryUpload";
import RepositoryList from "./RepositoryList";

export default function Repositories() {
  const { repositories, reposLoading, reposError, loadRepositories, refreshRepositories, deleteRepo, reingestRepo } = useWorkspace();

  useEffect(() => { refreshRepositories(); }, [refreshRepositories]);

  // Poll for in-progress ingestions
  useEffect(() => {
    const inProgress = repositories.some((r) => !["ready", "failed", "delete_failed"].includes(r.status));
    if (!inProgress) return;
    const t = setInterval(() => loadRepositories().catch(() => {}), 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repositories.map((r) => r.status).join(",")]);

  const remove = async (id) => {
    if (!window.confirm("Delete this repository and all its graph/vector data?")) return;
    try {
      await deleteRepo(id);
      toast.success("Deletion queued. The status updates when cleanup finishes.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to delete repository");
    }
  };

  const reingest = async (id) => {
    try {
      await reingestRepo(id);
      toast.success("Reingestion started");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to start reingestion");
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="repos-root">
      <div>
        <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// repositories"}</div>
        <h1 className="text-3xl font-semibold tracking-tighter mt-1" style={{ fontFamily: "Chivo" }}>Repositories</h1>
        <p className="text-sm text-white/50 mt-2">Connect a GitHub repo or upload a ZIP. Each one is parsed with tree-sitter, indexed into a knowledge graph, and made queryable.</p>
      </div>

      <RepositoryUpload />

      <RepositoryList
        repos={repositories}
        loading={reposLoading}
        error={reposError}
        onRetry={refreshRepositories}
        onReingest={reingest}
        onDelete={remove}
      />
    </div>
  );
}
