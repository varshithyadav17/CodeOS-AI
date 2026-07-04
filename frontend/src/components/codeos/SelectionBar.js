import { memo } from "react";
import { FileCode2, Network, GitFork, History, MessageSquareText, BookOpen, Files, X } from "lucide-react";
import { useWorkspace } from "../../context/WorkspaceContext";

const JUMPS = [
  { tab: "graph", label: "Graph", icon: Network },
  { tab: "arch", label: "Architecture", icon: GitFork },
  { tab: "timeline", label: "History", icon: History },
  { tab: "docs", label: "Docs", icon: BookOpen },
  { tab: "files", label: "Files", icon: Files },
];

function SelectionBar() {
  const { selectedFilePath, selectedNodeId, nodeById, clearSelection, setActiveTab, activeTab, askInChat } = useWorkspace();

  if (!selectedFilePath && !selectedNodeId) return null;

  const node = selectedNodeId ? nodeById.get(selectedNodeId) : null;
  const label = node?.qualified_name || node?.name || selectedFilePath;

  return (
    <div
      className="sticky top-0 z-20 flex items-center gap-2 bg-[#0F0F0F]/95 backdrop-blur border border-[#3FC8E8]/25 rounded-sm px-3 py-2 flex-wrap animate-in fade-in slide-in-from-top-1 duration-200"
      data-testid="workspace-selection-bar"
      role="status"
      aria-live="polite"
    >
      <FileCode2 size={13} className="text-[#3FC8E8] shrink-0" aria-hidden="true" />
      <div className="min-w-0 mr-1">
        <div className="text-xs mono text-white truncate max-w-[280px]" title={label}>{label}</div>
        {selectedFilePath && node?.qualified_name && (
          <div className="text-[10px] mono text-white/40 truncate max-w-[280px]">{selectedFilePath}</div>
        )}
      </div>
      <div className="flex items-center gap-1 flex-wrap" role="group" aria-label="Jump to related panel">
        {JUMPS.map((j) => {
          const Icon = j.icon;
          const isCurrent = activeTab === j.tab;
          return (
            <button
              key={j.tab}
              data-testid={`selection-jump-${j.tab}`}
              onClick={() => setActiveTab(j.tab)}
              aria-current={isCurrent}
              className={`text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] ${isCurrent ? "border-[#3FC8E8]/50 text-[#3FC8E8] bg-[#3FC8E8]/10" : "border-white/10 text-white/60 hover:text-white hover:border-white/30"}`}
            >
              <Icon size={10} aria-hidden="true" /> {j.label}
            </button>
          );
        })}
        <button
          data-testid="selection-jump-chat"
          onClick={() => askInChat(`Tell me about ${label}${selectedFilePath ? ` (${selectedFilePath})` : ""}.`)}
          className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
        >
          <MessageSquareText size={10} aria-hidden="true" /> Ask
        </button>
      </div>
      <button
        onClick={clearSelection}
        aria-label="Clear selection"
        className="ml-auto text-white/30 hover:text-white shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm transition-colors duration-150"
        data-testid="selection-clear"
        title="Clear selection (Esc)"
      >
        <X size={13} aria-hidden="true" />
      </button>
    </div>
  );
}

export default memo(SelectionBar);
