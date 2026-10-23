import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import { hasParsedWorkspace } from "../../lib/repositoryStatus";
import SearchIcon from "../../assets/icons/search.svg?react";
import NetworkIcon from "../../assets/icons/network.svg?react";
import MessageSquareTextIcon from "../../assets/icons/message-square-text.svg?react";
import GitForkIcon from "../../assets/icons/git-fork.svg?react";
import FileCode2Icon from "../../assets/icons/file-code-2.svg?react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { SkeletonList } from "../../components/Skeleton";
import { ErrorState } from "../../components/EmptyState";

const EXT_COLORS = { py: "#3572A5", js: "#F7DF1E", ts: "#3178C6", tsx: "#3178C6", jsx: "#61DAFB", go: "#00ADD8", rs: "#000", java: "#b07219", rb: "#701516", cs: "#178600", cpp: "#f34b7d", c: "#555", md: "#ffffff" };
function extOf(path) { return (path.split(".").pop() || "").toLowerCase(); }
function colorOf(path) { return EXT_COLORS[extOf(path)] || "rgba(255,255,255,0.4)"; }

export default function FilesPanel() {
  const {
    files, repoId, repo,
    selectedFilePath, selectFile, setActiveTab,
    highlightPaths, askInChat, fileNodeByPath,
  } = useWorkspace();
  const repoReady = hasParsedWorkspace(repo);

  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState({});
  const [fileContent, setFileContent] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState(null);

  useEffect(() => {
    if (!selectedFilePath || !repoId) { setFileContent(null); return; }
    const controller = new AbortController();
    setFileLoading(true); setFileError(null); setFileContent(null);
    api.get(`/repos/${repoId}/files/content`, { params: { path: selectedFilePath }, signal: controller.signal })
      .then((r) => { if (!controller.signal.aborted) setFileContent(r.data); })
      .catch((e) => { if (!controller.signal.aborted) setFileError(e?.response?.data?.detail || "Failed to load file."); })
      .finally(() => { if (!controller.signal.aborted) setFileLoading(false); });
    return () => controller.abort();
  }, [selectedFilePath, repoId]);

  const tree = useMemo(() => {
    const q = search.toLowerCase();
    const list = q ? files.filter((f) => f.path.toLowerCase().includes(q)) : files;
    const dirs = {};
    list.forEach((f) => {
      const parts = f.path.split("/");
      const dir = parts.length > 1 ? parts.slice(0, -1).join("/") : "";
      (dirs[dir] ||= []).push(f);
    });
    return dirs;
  }, [files, search]);

  if (!repoReady) return <div className="text-white/40 text-sm p-4">Waiting for ingestion to complete…</div>;
  if (files.length === 0) return <SkeletonList rows={8} rowClassName="h-7" />;

  return (
    <div className="grid grid-cols-12 gap-3" data-testid="files-panel">
      {/* File tree */}
      <div className="col-span-12 lg:col-span-4 glass-panel border border-white/10 rounded-xl flex flex-col h-[600px]">
        <div className="p-2 border-b border-white/10">
          <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1 focus-within:border-[#3FC8E8]">
            <SearchIcon width={11} height={11} className="text-white/40" aria-hidden="true" />
            <input
              data-testid="files-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter files…"
              className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30"
              aria-label="Filter files"
            />
          </div>
        </div>
        <div className="flex-1 overflow-auto text-xs" role="tree" aria-label="File tree">
          {Object.keys(tree).sort().map((dir) => (
            <div key={dir}>
              {dir && (
                <button
                  onClick={() => setExpanded((e) => ({ ...e, [dir]: !e[dir] }))}
                  className="w-full text-left px-3 py-1.5 mono text-white/40 hover:text-white flex items-center gap-1.5 focus-visible:outline-none"
                  aria-expanded={!expanded[dir]}
                  role="treeitem"
                >
                  <span className={`text-[9px] transition-transform ${expanded[dir] ? "" : "rotate-90"}`}>▶</span>
                  <span>{dir}/</span>
                </button>
              )}
              {(!dir || !expanded[dir]) && tree[dir].map((f) => (
                <button
                  key={f.path}
                  role="treeitem"
                  aria-selected={selectedFilePath === f.path}
                  data-testid={`file-${f.path}`}
                  onClick={() => selectFile(f.path)}
                  className={`w-full text-left ${dir ? "pl-7" : "pl-3"} pr-3 py-1 flex items-center gap-1.5 transition-colors duration-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] ${selectedFilePath === f.path ? "bg-[#3FC8E8]/10 text-[#3FC8E8]" : "text-white/70 hover:text-white hover:bg-white/[0.03]"} ${highlightPaths.has(f.path) ? "border-l-2 border-[#FF9100]" : ""}`}
                >
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colorOf(f.path) }} aria-hidden="true" />
                  <span className="mono truncate">{f.path.split("/").pop()}</span>
                  {f.loc && <span className="ml-auto text-[10px] text-white/30 shrink-0">{f.loc}</span>}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* File content + cross-panel nav */}
      <div className="col-span-12 lg:col-span-8 space-y-3">
        {selectedFilePath && (
          <div className="glass-panel border border-white/10 rounded-xl p-2 flex flex-wrap items-center gap-1.5" data-testid="files-crossnav">
            <span className="mono text-xs text-white/60 truncate max-w-[220px]" title={selectedFilePath}>{selectedFilePath}</span>
            <div className="ml-auto flex flex-wrap gap-1">
              {fileNodeByPath.has(selectedFilePath) && (
                <button data-testid="files-jump-graph" onClick={() => setActiveTab("graph")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/60"><NetworkIcon width={10} height={10} /> Graph</button>
              )}
              <button data-testid="files-jump-arch" onClick={() => setActiveTab("arch")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/60"><GitForkIcon width={10} height={10} /> Architecture</button>
              <button data-testid="files-jump-ask" disabled={repo?.status !== "ready"} title={repo?.status === "ready" ? "Ask about this file" : "Available when AI indexing finishes"} onClick={() => askInChat(`Explain what ${selectedFilePath} does and how it fits into the rest of the codebase.`)} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/60"><MessageSquareTextIcon width={10} height={10} /> Ask</button>
            </div>
          </div>
        )}
        <div className="glass-panel border border-white/10 rounded-xl h-[560px] overflow-auto" data-testid="file-content">
          {!selectedFilePath && (
            <div className="h-full flex items-center justify-center text-white/30 text-sm">
              <div className="text-center">
                <FileCode2Icon width={24} height={24} className="mx-auto mb-2 opacity-50" aria-hidden="true" />
                Select a file to view its content
              </div>
            </div>
          )}
          {selectedFilePath && fileLoading && <div className="p-4 text-white/40 text-sm animate-pulse">Loading…</div>}
          {selectedFilePath && fileError && <ErrorState message={fileError} testId="file-content-error" />}
          {selectedFilePath && !fileLoading && !fileError && fileContent && (
            <pre className="p-4 text-xs mono text-white/80 leading-relaxed whitespace-pre-wrap break-all" data-testid="file-content-pre">{fileContent.content}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
