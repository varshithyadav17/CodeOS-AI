import Loader2Icon from "../../assets/icons/loader-2.svg?react";

const SEV = { critical: "#FF3B30", high: "#FF9100", medium: "#FFB300", low: "#34C759", info: "#9CA3AF" };
const STATUS = { open: "#FFB300", in_progress: "#3FC8E8", resolved: "#34C759", wont_fix: "#9CA3AF" };

/** One card in the memory grid. */
export default function MemoryCard({ m, onClick }) {
  const pending = String(m.id).startsWith("optimistic-");
  return (
    <button
      onClick={onClick}
      data-testid={`memory-${m.id}`}
      disabled={pending}
      className={`text-left glass-panel border rounded-xl p-3 transition-colors duration-150 animate-in fade-in duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] ${pending ? "border-white/5 opacity-60" : "border-white/10 hover:border-white/30"}`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[9px] mono uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm border" style={{ color: SEV[m.severity] || "#fff", borderColor: `${SEV[m.severity] || "#fff"}55` }}>{m.severity}</span>
        <span className="text-[9px] mono uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm" style={{ color: STATUS[m.status], background: `${STATUS[m.status]}15` }}>{m.status.replace("_", " ")}</span>
        <span className="text-[9px] mono text-white/40 ml-auto">{pending ? <Loader2Icon width={10} height={10} className="animate-spin" aria-label="Saving" /> : m.category}</span>
      </div>
      <div className="text-sm text-white truncate" style={{ fontFamily: "Chivo" }}>{m.title}</div>
      {m.file_path && <div className="text-[10px] mono text-white/40 truncate mt-0.5">{m.file_path}</div>}
    </button>
  );
}

export { SEV, STATUS };
