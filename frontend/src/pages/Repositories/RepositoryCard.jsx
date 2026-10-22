import { Link } from "react-router-dom";
import GitBranchIcon from "../../assets/icons/git-branch.svg?react";
import FolderOpenIcon from "../../assets/icons/folder-open.svg?react";
import RefreshCwIcon from "../../assets/icons/refresh-cw.svg?react";
import Trash2Icon from "../../assets/icons/trash-2.svg?react";
import GithubIcon from "../../assets/icons/github.svg?react";

const statusColor = {
  queued: "text-white/50",
  cloning: "text-[#FFB300]",
  parsing: "text-[#FFB300]",
  embedding: "text-[#FFB300]",
  ready: "text-[#34C759]",
  failed: "text-[#FF3B30]",
  deleting: "text-[#FFB300]",
  delete_failed: "text-[#FF3B30]",
};

/** One row in the repositories list — status, stats, and reingest/delete
 * actions for a single repo. */
export default function RepositoryCard({ r, onReingest, onDelete }) {
  return (
    <li className="px-5 py-4 hover:bg-white/[0.02] transition-colors duration-150 animate-in fade-in duration-200" data-testid={`repo-item-${r.id}`}>
      <div className="flex items-start gap-4">
        <div className="w-9 h-9 rounded-sm bg-white/5 flex items-center justify-center mt-0.5">
          {r.source === "github" ? <GithubIcon width={16} height={16} className="text-white/70" aria-hidden="true" /> : <FolderOpenIcon width={16} height={16} className="text-white/70" aria-hidden="true" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <Link to={`/repositories/${r.id}`} data-testid={`repo-open-${r.id}`} className="text-white font-medium text-sm hover:text-[#3FC8E8] transition-colors truncate focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm">{r.name}</Link>
            <span className={`text-[10px] uppercase tracking-[0.18em] mono ${statusColor[r.status] || "text-white/50"}`}>{r.status}</span>
            {r.branch && <span className="text-[10px] mono text-white/40 flex items-center gap-1"><GitBranchIcon width={10} height={10} aria-hidden="true" />{r.branch}</span>}
          </div>
          {r.source_url && <div className="text-[11px] mono text-white/40 mt-0.5 truncate">{r.source_url}</div>}
          {!["ready", "failed", "delete_failed"].includes(r.status) && (
            <div className="mt-2 h-1 bg-white/5 rounded-sm overflow-hidden">
              <div className="h-full bg-[#3FC8E8] transition-all duration-300" style={{ width: `${r.progress || 0}%` }} />
            </div>
          )}
          {r.message && <div className="text-[11px] text-white/40 mt-1">{r.message}</div>}
          {r.status === "ready" && (
            <div className="flex flex-wrap gap-3 mt-2 text-[11px] mono text-white/50">
              <span>{r.stats?.files || 0} files</span>
              <span>{r.stats?.loc || 0} loc</span>
              <span>{r.stats?.nodes || 0} nodes</span>
              <span>{r.stats?.edges || 0} edges</span>
              <span>{r.stats?.chunks || 0} chunks</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button data-testid={`repo-reingest-${r.id}`} disabled={!["ready", "failed"].includes(r.status)} onClick={() => onReingest(r.id)} aria-label={`Reingest ${r.name}`} title="Reingest" className="p-2 hover:bg-white/5 rounded-sm text-white/50 hover:text-white transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"><RefreshCwIcon width={14} height={14} aria-hidden="true" /></button>
          <button data-testid={`repo-delete-${r.id}`} disabled={r.status === "deleting"} onClick={() => onDelete(r.id)} aria-label={`Delete ${r.name}`} title="Delete" className="p-2 hover:bg-white/5 rounded-sm text-white/50 hover:text-[#FF3B30] transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FF3B30]"><Trash2Icon width={14} height={14} aria-hidden="true" /></button>
        </div>
      </div>
    </li>
  );
}
