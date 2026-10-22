import XIcon from "../../assets/icons/x.svg?react";
import ExternalLinkIcon from "../../assets/icons/external-link.svg?react";
import { useNavigate } from "react-router-dom";

/** Right-side drawer showing a single memory's full detail: description,
 * file/symbol, tags, status toggle, and delete. */
export default function MemoryDetail({ selected, onClose, onUpdate, onDelete }) {
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex justify-end animate-in fade-in duration-150" onClick={onClose} data-testid="memory-drawer">
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="memory-drawer-title"
        className="w-full max-w-md glass-panel-soft border-l border-white/10 h-full overflow-auto p-5 animate-in slide-in-from-right duration-200"
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">{selected.category}</div>
            <h2 id="memory-drawer-title" className="text-lg tracking-tight font-medium mt-1" style={{ fontFamily: "Chivo" }}>{selected.title}</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm"><XIcon width={16} height={16} aria-hidden="true" /></button>
        </div>
        <p className="text-sm text-white/70 whitespace-pre-wrap leading-relaxed">{selected.description || "No description."}</p>
        {selected.file_path && <div className="text-[11px] mono text-white/50 mt-3">{selected.file_path}{selected.symbol ? ` · ${selected.symbol}` : ""}</div>}
        {(selected.file_path || selected.symbol) && (
          <button
            data-testid="memory-open-workspace"
            onClick={() => {
              const params = new URLSearchParams();
              if (selected.file_path) params.set("file", selected.file_path);
              if (selected.symbol) params.set("symbol", selected.symbol);
              navigate(`/repositories/${selected.repo_id}?${params.toString()}`);
            }}
            className="mt-3 text-xs mono flex items-center gap-1.5 text-[#3FC8E8] hover:text-white border border-[#3FC8E8]/40 hover:bg-[#3FC8E8]/10 px-2.5 py-1.5 rounded-sm w-fit transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
          >
            <ExternalLinkIcon width={12} height={12} aria-hidden="true" /> Open in workspace
          </button>
        )}
        {selected.tags?.length > 0 && <div className="flex gap-1 flex-wrap mt-3">{selected.tags.map((t) => <span key={t} className="text-[10px] mono bg-white/5 px-1.5 py-0.5 rounded-sm text-white/60">{t}</span>)}</div>}
        <div className="mt-5 space-y-2">
          <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Status</div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Change status">
            {["open", "in_progress", "resolved", "wont_fix"].map((s) => (
              <button key={s} data-testid={`memory-status-${s}`} aria-pressed={selected.status === s} onClick={() => onUpdate(selected.id, { status: s })} className={`text-xs mono uppercase tracking-[0.16em] px-2 py-1 rounded-sm border transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] ${selected.status === s ? "border-[#3FC8E8] text-[#3FC8E8]" : "border-white/10 text-white/60 hover:border-white/30"}`}>{s.replace("_", " ")}</button>
            ))}
          </div>
        </div>
        <button data-testid="memory-delete" onClick={() => onDelete(selected.id)} className="mt-6 text-xs text-[#FF3B30] hover:text-white border border-[#FF3B30]/40 hover:bg-[#FF3B30] px-3 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FF3B30]">Delete memory</button>
      </div>
    </div>
  );
}
