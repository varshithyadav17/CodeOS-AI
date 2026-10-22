import FileCode2Icon from "../../assets/icons/file-code-2.svg?react";
import NetworkIcon from "../../assets/icons/network.svg?react";
import GitForkIcon from "../../assets/icons/git-fork.svg?react";
import MessageSquareTextIcon from "../../assets/icons/message-square-text.svg?react";
import FilesIcon from "../../assets/icons/files.svg?react";
import XIcon from "../../assets/icons/x.svg?react";
import { useWorkspace } from "../../context/WorkspaceContext";

const JUMPS = [
  { tab: "files",  icon: FileCode2Icon,        label: "Files" },
  { tab: "graph",  icon: NetworkIcon,           label: "Graph" },
  { tab: "arch",   icon: GitForkIcon,           label: "Architecture" },
  { tab: "review", icon: FilesIcon,             label: "Review" },
  { tab: "chat",   icon: MessageSquareTextIcon, label: "Chat" },
];

export default function SelectionBar() {
  const { selectedFilePath, selectedNodeId, clearSelection, nodeById, setActiveTab } = useWorkspace();
  const label = selectedFilePath || (selectedNodeId && nodeById.get(selectedNodeId)?.name) || selectedNodeId;

  if (!selectedFilePath && !selectedNodeId) return null;

  return (
    <div
      data-testid="selection-bar"
      role="toolbar"
      aria-label="Selected item navigation"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 glass-panel border border-[#3FC8E8]/30 rounded-xl px-3 py-2 flex items-center gap-2 shadow-[0_8px_30px_-4px_rgba(63,200,232,0.3)] animate-in slide-in-from-bottom duration-200"
    >
      <span className="text-[10px] mono text-[#3FC8E8] max-w-[180px] truncate" title={label}>{label}</span>
      <div className="h-3.5 w-px bg-white/10" />
      {JUMPS.map(({ tab, icon: Icon, label: lbl }) => (
        <button
          key={tab}
          data-testid={`selection-jump-${tab}`}
          onClick={() => setActiveTab(tab)}
          aria-label={`Jump to ${lbl}`}
          title={lbl}
          className="p-1.5 rounded-sm text-white/50 hover:text-[#3FC8E8] hover:bg-[#3FC8E8]/10 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
        >
          <Icon width={13} height={13} aria-hidden="true" />
        </button>
      ))}
      <div className="h-3.5 w-px bg-white/10" />
      <button
        data-testid="selection-clear"
        onClick={clearSelection}
        aria-label="Clear selection"
        className="p-1.5 rounded-sm text-white/50 hover:text-white hover:bg-white/10 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
      >
        <XIcon width={13} height={13} aria-hidden="true" />
      </button>
    </div>
  );
}
