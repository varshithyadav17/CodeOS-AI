import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import Loader2Icon from "../../assets/icons/loader-2.svg?react";
import ArrowLeftIcon from "../../assets/icons/arrow-left.svg?react";
import GitBranchIcon from "../../assets/icons/git-branch.svg?react";
import FileCode2Icon from "../../assets/icons/file-code-2.svg?react";
import NetworkIcon from "../../assets/icons/network.svg?react";
import { useWorkspace } from "../../context/WorkspaceContext";

const STATS = [
  { l: "Files", k: "files", i: FileCode2Icon },
  { l: "Nodes", k: "nodes", i: NetworkIcon },
  { l: "Edges", k: "edges", i: NetworkIcon },
  { l: "Chunks", k: "chunks", i: FileCode2Icon },
];

/** Top bar for the repository workspace page: repo name, status, and
 * a row of stats that update as ingestion progresses. Reads `repo` and
 * `reingestRepo` from WorkspaceContext so the parent doesn't need to
 * pass callbacks down as props. */
export default function WorkspaceHeader({ repo }) {
  const { reingestRepo } = useWorkspace();
  const prevStatus = useRef(repo?.status);

  useEffect(() => {
    prevStatus.current = repo?.status;
  }, [repo?.status]);

  const handleReingest = async () => {
    if (!repo?.id) return;
    try {
      await reingestRepo(repo.id);
      toast.success("Reingestion started");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to start reingestion");
    }
  };

  if (!repo) return null;

  const running = ["queued", "cloning", "parsing", "embedding", "deleting"].includes(repo.status);

  return (
    <div className="border-b border-white/10 px-6 py-3 flex items-center gap-4 flex-wrap" data-testid="workspace-header">
      <Link to="/repositories" className="text-white/50 hover:text-white transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm" aria-label="Back to repositories">
        <ArrowLeftIcon width={16} height={16} aria-hidden="true" />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg tracking-tight font-semibold truncate" style={{ fontFamily: "Chivo" }} data-testid="workspace-repo-name">{repo.name}</h1>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-white/50" data-testid="workspace-repo-status">{repo.status}</span>
          {running && <Loader2Icon width={12} height={12} className="animate-spin text-[#3FC8E8]" aria-hidden="true" aria-label="Ingestion in progress" />}
          {repo.branch && (
            <span className="text-[10px] mono text-white/40 flex items-center gap-1">
              <GitBranchIcon width={10} height={10} aria-hidden="true" />{repo.branch}
            </span>
          )}
        </div>
        {repo.status !== "ready" && repo.status !== "failed" && (
          <div className="mt-1 h-0.5 bg-white/5 rounded-sm overflow-hidden w-48">
            <div className="h-full bg-[#3FC8E8] transition-all duration-300" style={{ width: `${repo.progress || 0}%` }} />
          </div>
        )}
      </div>
      {repo.message && repo.status !== "ready" && <p role="status" className="text-xs text-white/60 w-full">{repo.message}</p>}
      {["failed", "delete_failed"].includes(repo.status) && <Link to="/repositories" className="text-xs text-[#3FC8E8]">Open repositories to retry or delete</Link>}
      {repo.status === "ready" && (
        <div className="flex items-center gap-4 text-xs">
          {STATS.map(({ l, k, i: StatIcon }) => (
            <div key={k} className="flex items-center gap-1.5 text-white/50" data-testid={`workspace-stat-${k}`}>
              <StatIcon width={11} height={11} aria-hidden="true" />
              <span className="mono">{repo.stats?.[k] ?? 0} {l}</span>
            </div>
          ))}
          <button
            data-testid="workspace-reingest"
            onClick={handleReingest}
            className="text-xs mono border border-white/10 hover:border-white/30 text-white/60 hover:text-white px-2 py-1 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
          >
            Re-ingest
          </button>
        </div>
      )}
    </div>
  );
}
