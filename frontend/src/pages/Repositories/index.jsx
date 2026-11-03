import { useEffect } from "react";
import { toast } from "sonner";
import { useWorkspace } from "../../context/WorkspaceContext";
import RepositoryUpload from "./RepositoryUpload";
import RepositoryList from "./RepositoryList";
import "../workspace.css";

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
    <div className="workspace-page space-y-6" data-testid="repos-root">
      <header className="workspace-page-heading"><div><h1>Repositories</h1>
        <p>Bring in a codebase, then explore its files, relationships, and saved findings.</p>
      </div></header>

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
