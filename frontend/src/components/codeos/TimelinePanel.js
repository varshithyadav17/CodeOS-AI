import { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Loader2, GitCommit, Flame, Users, TrendingUp, FileClock, Search as SearchIcon, MessageSquareText, Network } from "lucide-react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { SkeletonList } from "../ui/skeleton";
import { EmptyState, ErrorState } from "../ui/state";

const TABS = [
  { k: "commits", label: "Commits", icon: GitCommit },
  { k: "hotspots", label: "Hotspots", icon: Flame },
  { k: "contributors", label: "Contributors", icon: Users },
  { k: "complexity", label: "Complexity", icon: TrendingUp },
  { k: "file", label: "File history", icon: FileClock },
];

const TAB_URL = {
  commits: (id) => [`/repos/${id}/timeline/commits`, { limit: 200 }],
  hotspots: (id) => [`/repos/${id}/timeline/hotspots`, { limit: 80 }],
  contributors: (id) => [`/repos/${id}/timeline/contributors`, {}],
  complexity: (id) => [`/repos/${id}/timeline/complexity`, { buckets: 20 }],
};

export default function TimelinePanel({ repoId }) {
  const { files, selectedFilePath, selectFile, setHighlightPaths, askInChat, fileNodeByPath, setActiveTab } = useWorkspace();
  // Land straight on "File history" if something is already selected
  // elsewhere in the workspace (Files, Graph, Architecture, Chat context…) —
  // this is what makes "Timeline filters by the affected file" actually work.
  const [tab, setTab] = useState(() => (selectedFilePath ? "file" : "commits"));
  const [data, setData] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [filePath, setFilePath] = useState(selectedFilePath || "");
  const [fileHistory, setFileHistory] = useState(null);
  const [fileError, setFileError] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);

  const loadFileHistory = useCallback(async (path) => {
    if (!path.trim()) return;
    setFileLoading(true);
    setFileError(null);
    try {
      const r = await api.get(`/repos/${repoId}/timeline/file`, { params: { path: path.trim() } });
      setFileHistory(r.data);
    } catch (e) {
      setFileHistory(null);
      setFileError(e?.response?.data?.detail || "Couldn't load history for that path.");
    } finally {
      setFileLoading(false);
    }
  }, [repoId]);

  // React to a file being selected elsewhere in the workspace while this
  // panel is mounted (e.g. user is already on the Timeline tab and clicks a
  // different file's node in the Knowledge Graph in another render pass —
  // uncommon since tabs unmount, but also covers the initial mount case).
  useEffect(() => {
    if (!selectedFilePath) return;
    setFilePath(selectedFilePath);
    setTab("file");
    loadFileHistory(selectedFilePath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFilePath]);

  const loadTab = useCallback((t, signal) => {
    if (t === "file" || !TAB_URL[t]) return;
    setLoading(true);
    setErrors((e) => (e[t] == null ? e : { ...e, [t]: null }));
    const [url, params] = TAB_URL[t](repoId);
    api.get(url, { params, signal })
      .then((r) => {
        setData((d) => ({ ...d, [t]: r.data }));
        // Cross-panel: as soon as hotspot data lands, flag those files in
        // the Files panel so "high-churn" status is visible everywhere.
        if (t === "hotspots" && r.data?.items) {
          setHighlightPaths(r.data.items.map((h) => h.path));
        }
      })
      .catch((e) => {
        if (signal?.aborted || e.code === "ERR_CANCELED") return;
        setErrors((er) => ({ ...er, [t]: e?.response?.data?.detail || "Failed to load." }));
      })
      .finally(() => { if (!signal?.aborted) setLoading(false); });
  }, [repoId, setHighlightPaths]);

  useEffect(() => {
    if (tab === "file" || data[tab] || errors[tab]) return;
    const controller = new AbortController();
    loadTab(tab, controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, data, errors]);

  const retryTab = (t) => setErrors((e) => ({ ...e, [t]: null }));

  const filter = (list, fields) => {
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter((x) => fields.some((f) => String(x[f] || "").toLowerCase().includes(q)));
  };

  const openFileHistory = (path) => {
    selectFile(path);
    setFilePath(path);
    setTab("file");
    loadFileHistory(path);
  };

  const selectedHasGraphNode = filePath && fileNodeByPath.has(filePath);

  return (
    <div className="space-y-3" data-testid="timeline-panel">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex border border-white/10 rounded-sm overflow-hidden" data-testid="timeline-tabs" role="tablist">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.k}
                data-testid={`timeline-tab-${t.k}`}
                onClick={() => setTab(t.k)}
                role="tab"
                aria-selected={tab === t.k}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] ${tab === t.k ? "bg-[#3FC8E8] text-black" : "glass-panel text-white/60 hover:text-white"}`}
              >
                <Icon size={12} aria-hidden="true" /> {t.label}
              </button>
            );
          })}
        </div>
        <label htmlFor="timeline-search-input" className="sr-only">Search timeline entries</label>
        <input
          id="timeline-search-input"
          data-testid="timeline-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search…"
          className={`glass-panel-soft border border-white/10 rounded-xl text-xs mono px-2 py-1.5 text-white flex-1 max-w-xs outline-none focus-visible:border-[#3FC8E8] ${tab === "file" ? "hidden" : ""}`}
        />
      </div>

      {loading && !errors[tab] && <SkeletonList rows={5} rowClassName="h-10" />}

      {!loading && errors[tab] && (
        <ErrorState message={errors[tab]} onRetry={() => retryTab(tab)} testId={`timeline-${tab}-error`} />
      )}

      {!loading && !errors.commits && tab === "commits" && data.commits && (
        data.commits.available === false ? (
          <EmptyState title="Git history not available." subtitle="This repository was uploaded as a ZIP without .git, so commit history can't be shown." testId="timeline-unavailable" />
        ) : filter(data.commits.commits, ["sha", "author", "message"]).length === 0 ? (
          <EmptyState title={search ? `No commits match "${search}".` : "No commits found."} testId="timeline-commits-empty" />
        ) : (
        <div className="glass-panel border border-white/10 rounded-xl" data-testid="timeline-commits">
          <div className="px-4 py-2 border-b border-white/10 flex justify-between text-[10px] mono uppercase tracking-[0.18em] text-white/40"><span>{filter(data.commits.commits, ["sha", "author", "message"]).length} commits</span></div>
          <ul className="divide-y divide-white/10 max-h-[520px] overflow-auto">
            {filter(data.commits.commits, ["sha", "author", "message"]).map((c) => (
              <li key={c.sha} data-testid={`commit-${c.sha}`}>
                <button
                  onClick={() => askInChat(`Explain what changed in commit ${c.sha} ("${c.message}") by ${c.author}.`)}
                  className="w-full text-left px-4 py-2.5 hover:bg-white/[0.02] transition-colors duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-[-1px]"
                  title="Ask the AI about this commit"
                >
                  <div className="flex items-start gap-3">
                    <span className="mono text-[#3FC8E8] text-[10px] mt-0.5">{c.sha}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-white truncate">{c.message}</div>
                      <div className="text-[10px] mono text-white/40 mt-0.5">{c.author} · {new Date(c.date).toLocaleString()}</div>
                    </div>
                    <div className="text-[10px] mono whitespace-nowrap"><span className="text-[#34C759]">+{c.insertions}</span> <span className="text-[#FF3B30]">-{c.deletions}</span></div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
        )
      )}

      {!loading && !errors.hotspots && tab === "hotspots" && data.hotspots && (
        filter(data.hotspots.items, ["path"]).length === 0 ? (
          <EmptyState title={search ? `No hotspots match "${search}".` : "No high-churn files detected."} testId="timeline-hotspots-empty" />
        ) : (
        <div className="glass-panel border border-white/10 rounded-xl" data-testid="timeline-hotspots">
          <div className="px-4 py-2 border-b border-white/10 text-[10px] mono uppercase tracking-[0.18em] text-white/40">High-churn files (likely refactor candidates) · click a row to see its history</div>
          <ul className="divide-y divide-white/10 max-h-[520px] overflow-auto">
            {filter(data.hotspots.items, ["path"]).map((h, i) => {
              const max = data.hotspots.items[0]?.changes || 1;
              return (
                <li key={h.path}>
                  <button
                    onClick={() => openFileHistory(h.path)}
                    className="w-full text-left px-4 py-2 hover:bg-white/[0.03] transition-colors duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-[-1px]"
                    data-testid={`hotspot-${i}`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="mono truncate text-white/80">{h.path}</span>
                      <span className="text-[10px] mono text-white/40 ml-3">{h.changes} changes · {h.authors} authors</span>
                    </div>
                    <div className="h-1 bg-white/5 rounded-sm overflow-hidden mt-1.5"><div className="h-full bg-gradient-to-r from-[#FFB300] to-[#FF3B30] transition-all duration-300" style={{ width: `${(h.changes / max) * 100}%` }} /></div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
        )
      )}

      {!loading && !errors.contributors && tab === "contributors" && data.contributors && (
        filter(data.contributors.items, ["author", "email"]).length === 0 ? (
          <EmptyState title={search ? `No contributors match "${search}".` : "No contributor data available."} testId="timeline-contributors-empty" />
        ) : (
        <div className="glass-panel border border-white/10 rounded-xl" data-testid="timeline-contributors">
          <ul className="divide-y divide-white/10 max-h-[520px] overflow-auto">
            {filter(data.contributors.items, ["author", "email"]).map((c) => (
              <li key={c.author} className="px-4 py-2.5 flex items-center gap-3">
                <div className="w-7 h-7 rounded-sm bg-white/10 text-[10px] flex items-center justify-center mono" aria-hidden="true">{c.author.slice(0, 2).toUpperCase()}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-white truncate">{c.author}</div>
                  <div className="text-[10px] mono text-white/40 truncate">{c.email}</div>
                </div>
                <div className="text-[10px] mono whitespace-nowrap">{c.commits} commits · <span className="text-[#34C759]">+{c.insertions}</span> <span className="text-[#FF3B30]">-{c.deletions}</span></div>
              </li>
            ))}
          </ul>
        </div>
        )
      )}

      {!loading && !errors.complexity && tab === "complexity" && data.complexity && (
        (data.complexity.trend || []).length === 0 ? (
          <EmptyState title="No complexity trend data available." testId="timeline-complexity-empty" />
        ) : (
        <div className="glass-panel border border-white/10 rounded-xl p-4" data-testid="timeline-complexity">
          <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40 mb-3">Code churn over time (insertions + deletions per period)</div>
          <div className="flex items-end gap-1 h-48">
            {data.complexity.trend.map((b, i, arr) => {
              const max = Math.max(...arr.map((x) => x.churn), 1);
              return (
                <div key={i} className="flex-1 group relative" data-testid={`complexity-bucket-${i}`}>
                  <div className="bg-[#3FC8E8] hover:bg-[#52D4F0] transition-colors duration-150 rounded-t-sm" style={{ height: `${(b.churn / max) * 100}%` }} />
                  <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block bg-black border border-white/10 rounded-sm px-2 py-1 text-[10px] mono whitespace-nowrap z-10">
                    {new Date(b.from).toLocaleDateString()} · {b.commits} commits · {b.churn} churn
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        )
      )}

      {!loading && tab === "file" && (
        <div className="grid grid-cols-12 gap-3" data-testid="timeline-file">
          <div className="col-span-12 lg:col-span-8 space-y-3">
            <form
              onSubmit={(e) => { e.preventDefault(); selectFile(filePath); loadFileHistory(filePath); }}
              className="flex items-center gap-2"
            >
              <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1.5 flex-1 focus-within:border-[#3FC8E8]">
                <SearchIcon size={12} className="text-white/40" aria-hidden="true" />
                <label htmlFor="timeline-file-path-input" className="sr-only">File path</label>
                <input
                  id="timeline-file-path-input"
                  data-testid="timeline-file-path-input"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  list="timeline-known-files"
                  placeholder="src/services/foo.py"
                  className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30"
                />
                {files.length > 0 && (
                  <datalist id="timeline-known-files">
                    {files.map((f) => <option key={f.path} value={f.path} />)}
                  </datalist>
                )}
              </div>
              <button data-testid="timeline-file-lookup" type="submit" disabled={fileLoading || !filePath.trim()} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black px-3 py-1.5 rounded-lg text-xs transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px">
                {fileLoading ? <Loader2 size={12} className="animate-spin" aria-hidden="true" /> : "Look up"}
              </button>
            </form>

            {fileLoading && <SkeletonList rows={4} rowClassName="h-10" />}

            {!fileLoading && fileError && (
              <ErrorState message={fileError} onRetry={() => loadFileHistory(filePath)} testId="timeline-file-error" />
            )}

            {!fileLoading && !fileError && fileHistory && (
              fileHistory.history?.length === 0 ? (
                <EmptyState title="No commit history found for this path." testId="timeline-file-empty" />
              ) : (
                <div className="glass-panel border border-white/10 rounded-xl animate-in fade-in duration-200" data-testid="timeline-file-list">
                  <div className="px-4 py-2 border-b border-white/10 text-[10px] mono uppercase tracking-[0.18em] text-white/40">{fileHistory.history.length} revisions · {filePath}</div>
                  <ul className="divide-y divide-white/10 max-h-[520px] overflow-auto">
                    {fileHistory.history.map((h, i) => (
                      <li key={i} className="px-4 py-2.5" data-testid={`file-history-${i}`}>
                        <div className="flex items-start gap-3">
                          <span className="mono text-[#3FC8E8] text-[10px] mt-0.5">{h.sha}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs text-white truncate">{h.message}</div>
                            <div className="text-[10px] mono text-white/40 mt-0.5">{h.author} · {new Date(h.date).toLocaleString()}</div>
                          </div>
                          <div className="text-[10px] mono whitespace-nowrap"><span className="text-[#34C759]">+{h.insertions}</span> <span className="text-[#FF3B30]">-{h.deletions}</span></div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            )}

            {!fileLoading && !fileError && !fileHistory && (
              <EmptyState title="Enter a file path to see its commit-by-commit evolution." testId="timeline-file-prompt" />
            )}
          </div>

          {/* Cross-panel quick actions for the file currently under the microscope */}
          <div className="col-span-12 lg:col-span-4 glass-panel border border-white/10 rounded-xl p-4 h-fit space-y-1.5" data-testid="timeline-file-actions">
            <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40 mb-2">Jump to</div>
            <button
              data-testid="timeline-action-graph"
              disabled={!selectedHasGraphNode}
              onClick={() => { selectFile(filePath); setActiveTab("graph"); }}
              className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] disabled:opacity-40 text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
            >
              <Network size={12} aria-hidden="true" /> Knowledge Graph
            </button>
            <button
              data-testid="timeline-action-chat"
              disabled={!filePath.trim()}
              onClick={() => askInChat(`What changed most in ${filePath} historically, and why might it be high-churn?`)}
              className="w-full flex items-center gap-2 text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] disabled:opacity-40 text-white/70 px-2.5 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
            >
              <MessageSquareText size={12} aria-hidden="true" /> Ask about this file
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
