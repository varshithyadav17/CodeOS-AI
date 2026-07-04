import { memo, useMemo, useState } from "react";
import { Search, Flame, Network, MessageSquareText, History, BookOpen, GitFork, FileCode2 } from "lucide-react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { EmptyState } from "../ui/state";

const FileRow = memo(function FileRow({ f, index, active, hot, onSelect }) {
  return (
    <li>
      <button
        data-testid={`file-row-${index}`}
        onClick={onSelect}
        aria-current={active}
        className={`w-full text-left px-4 py-2 text-xs mono flex justify-between items-center gap-2 transition-colors duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-[-1px] ${active ? "bg-[#3FC8E8]/10 border-l-2 border-[#3FC8E8]" : "border-l-2 border-transparent hover:bg-white/[0.03]"}`}
      >
        <span className="truncate flex items-center gap-1.5 text-white/80">
          {hot && <Flame size={10} className="text-[#FF9100] shrink-0" aria-label="High churn" />}
          {f.path}
        </span>
        <span className="text-white/40 shrink-0 ml-3">{f.language} · {f.loc}</span>
      </button>
    </li>
  );
});

export default function FilesPanel() {
  const { files, selectedFilePath, selectFile, highlightPaths, askInChat, fileNodeByPath, setActiveTab } = useWorkspace();
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return files;
    const q = search.toLowerCase();
    return files.filter((f) => f.path.toLowerCase().includes(q));
  }, [files, search]);

  const selectedFile = files.find((f) => f.path === selectedFilePath);
  const hasGraphNode = selectedFilePath && fileNodeByPath.has(selectedFilePath);

  if (files.length === 0) {
    return <EmptyState icon={FileCode2} title="No files were indexed for this repository." testId="files-panel-empty" />;
  }

  return (
    <div className="grid grid-cols-12 gap-3" data-testid="files-panel">
      <div className="col-span-12 lg:col-span-8 glass-panel border border-white/10 rounded-xl" data-testid="files-list">
        <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2">
          <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1.5 flex-1 focus-within:border-[#3FC8E8]">
            <Search size={12} className="text-white/40" aria-hidden="true" />
            <label htmlFor="files-search-input" className="sr-only">Filter files</label>
            <input
              id="files-search-input"
              data-testid="files-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter files…"
              className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30"
            />
          </div>
          <span className="text-[10px] mono text-white/40 whitespace-nowrap">{filtered.length} / {files.length}</span>
        </div>
        <div className="px-4 py-2 border-b border-white/10 text-[10px] mono uppercase tracking-[0.18em] text-white/50 flex justify-between">
          <span>Path</span><span>Lang · LOC</span>
        </div>
        {filtered.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title={`No files match "${search}".`}
              action={{ label: "Clear filter", onClick: () => setSearch("") }}
              testId="files-search-empty"
            />
          </div>
        ) : (
          <ul className="divide-y divide-white/10 max-h-[560px] overflow-auto" role="list">
            {filtered.map((f, i) => (
              <FileRow
                key={f.path}
                f={f}
                index={i}
                active={f.path === selectedFilePath}
                hot={highlightPaths.has(f.path)}
                onSelect={() => selectFile(f.path)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Selection detail / quick actions */}
      <div className="col-span-12 lg:col-span-4 glass-panel border border-white/10 rounded-xl p-4 h-fit lg:sticky lg:top-4" data-testid="files-detail">
        {!selectedFile ? (
          <div className="text-white/40 text-xs">Select a file to see quick actions — jump to its graph node, ask about it in chat, or view its commit history.</div>
        ) : (
          <div className="space-y-3 animate-in fade-in duration-150" key={selectedFile.path}>
            <div>
              <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Selected file</div>
              <div className="text-sm mono text-white break-all mt-1">{selectedFile.path}</div>
              <div className="text-[11px] text-white/40 mt-0.5">{selectedFile.language} · {selectedFile.loc} lines</div>
            </div>
            <div className="space-y-1.5">
              <button
                data-testid="files-action-graph"
                disabled={!hasGraphNode}
                onClick={() => setActiveTab("graph")}
                className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] disabled:opacity-40 disabled:hover:border-white/10 disabled:hover:text-white text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <Network size={12} aria-hidden="true" /> View in Knowledge Graph
              </button>
              <button
                data-testid="files-action-arch"
                disabled={!hasGraphNode}
                onClick={() => setActiveTab("arch")}
                className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] disabled:opacity-40 disabled:hover:border-white/10 disabled:hover:text-white text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <GitFork size={12} aria-hidden="true" /> View in Architecture
              </button>
              <button
                data-testid="files-action-chat"
                onClick={() => askInChat(`Tell me about ${selectedFile.path} — what does it do, and what depends on it?`)}
                className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <MessageSquareText size={12} aria-hidden="true" /> Ask about this file
              </button>
              <button
                data-testid="files-action-history"
                onClick={() => setActiveTab("timeline")}
                className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <History size={12} aria-hidden="true" /> View commit history
              </button>
              <button
                data-testid="files-action-docs"
                onClick={() => setActiveTab("docs")}
                className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <BookOpen size={12} aria-hidden="true" /> Open documentation
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
