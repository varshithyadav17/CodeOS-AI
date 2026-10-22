import { useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { useWorkspace } from "../../context/WorkspaceContext";
import { EmptyState, ErrorState } from "../../components/EmptyState";
import { SkeletonList } from "../../components/Skeleton";

const VIEWS = [["commits", "Commits"], ["hotspots", "Hotspots"], ["contributors", "Contributors"],
  ["complexity", "Code churn"], ["file", "File history"]];
const date = (value) => value ? new Date(value).toLocaleDateString() : "Date unavailable";
const actionStyle = "rounded border border-white/15 px-3 py-1.5 text-xs text-[#3FC8E8] hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed";

function CommitList({ items }) {
  return <ul className="divide-y divide-white/10" data-testid="timeline-commits">
    {items.map((commit) => <li key={commit.sha} className="py-3 space-y-1">
      <p className="text-sm text-white/85 break-words">{commit.message || "Commit"}</p>
      <div className="flex flex-wrap gap-3 text-xs text-white/45">
        <code>{commit.sha}</code><span>{commit.author}</span><time>{date(commit.date)}</time>
        {commit.stats_available === false ? <span>Change counts unavailable</span> : <>
          <span className="text-emerald-300">+{commit.insertions || 0}</span>
          <span className="text-red-300">−{commit.deletions || 0}</span>
        </>}
      </div>
    </li>)}
  </ul>;
}

export default function TimelinePanel({ repoId }) {
  const { files, selectedFilePath, selectFile, setHighlightPaths, setActiveTab, knownFilePaths } = useWorkspace();
  const [view, setView] = useState("commits");
  const [query, setQuery] = useState("");
  const [path, setPath] = useState(selectedFilePath || "");
  const metadata = useFetch(`/repos/${repoId}/timeline/commits`);
  const detail = useFetch(`/repos/${repoId}/timeline/${view}`, {
    enabled: !!metadata.data?.available && view !== "commits" && (view !== "file" || !!path),
    params: view === "file" ? { path } : undefined,
  });
  const current = view === "commits" ? metadata : detail;
  const data = current.data;
  const items = (view === "commits" ? data?.commits : view === "file" ? data?.history : view === "complexity" ? data?.trend : data?.items) || [];
  const visible = items.filter((item) => [item.message, item.sha, item.author, item.email, item.path].some((value) => String(value || "").toLowerCase().includes(query.toLowerCase())));
  const openHistory = (filePath) => { setPath(filePath); setQuery(""); setView("file"); selectFile(filePath); };

  if (metadata.loading) return <SkeletonList />;
  if (metadata.error) return <ErrorState testId="timeline-error" message={metadata.error} onRetry={metadata.retry} />;
  if (!metadata.data?.available) return <EmptyState testId="timeline-unavailable" title="Git history is not included in this upload"
    subtitle="Add a repository from GitHub to view its available commit history. ZIP uploads still support code analysis, reviews, and documentation." />;

  return <section className="glass-panel rounded-xl border border-white/10 p-4 md:p-5 space-y-4" data-testid="timeline-root" aria-label="Repository timeline">
    <div>
      <h2 className="text-lg font-medium">Repository timeline</h2>
      <p className="mt-1 text-xs text-white/50" data-testid="timeline-scope">
        {metadata.data.shallow ? "Limited history: this snapshot comes from a shallow clone. Older commits and complete file history may be missing." : "History captured during the last repository analysis."}
        {" "}Change counts describe the captured history; historical source diffs are not stored.
      </p>
    </div>
    <div className="flex flex-wrap gap-2" role="group" aria-label="Timeline views">
      {VIEWS.map(([key, label]) => <button key={key} type="button" data-testid={`timeline-view-${key}`} aria-pressed={view === key}
        onClick={() => { setView(key); setQuery(""); }}
        className={`${actionStyle} ${view === key ? "bg-[#3FC8E8]/10 border-[#3FC8E8]/50" : "text-white/60"}`}>{label}</button>)}
    </div>
    {view !== "complexity" && <input type="search" aria-label="Search timeline" value={query} onChange={(event) => setQuery(event.target.value)}
      placeholder="Search this view…" className="w-full rounded border border-white/15 bg-black/20 px-3 py-2 text-sm" />}
    {view === "file" && <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="timeline-file" className="text-xs text-white/60">File</label>
      <select id="timeline-file" value={path} onChange={(event) => { setPath(event.target.value); selectFile(event.target.value); }}
        className="min-w-0 max-w-full flex-1 rounded border border-white/15 bg-[#121212] p-2 text-sm">
        <option value="">Choose a file</option>
        {path && !knownFilePaths.has(path) && <option value={path}>{path} (historical)</option>}
        {files.map((file) => <option key={file.path} value={file.path}>{file.path}</option>)}
      </select>
      <button type="button" className={actionStyle} disabled={!knownFilePaths.has(path)} onClick={() => selectFile(path, { tab: "files" })}>Open current source</button>
    </div>}
    {view === "file" && !path ? <EmptyState title="Choose a file to see its captured history" />
      : current.loading ? <SkeletonList /> : current.error ? <ErrorState testId="timeline-detail-error" message={current.error} onRetry={current.retry} />
      : !items.length ? <EmptyState title="No history captured for this view" subtitle="The repository snapshot may contain only a recent commit or a limited set of file histories." />
      : view !== "complexity" && !visible.length ? <EmptyState title="No matching history" /> : <>
        {(view === "commits" || view === "file") && <CommitList items={visible} />}
        {view === "hotspots" && <>
          <button type="button" className={actionStyle} onClick={() => { setHighlightPaths(visible.map((item) => item.path)); setActiveTab("files"); }}>Highlight these files</button>
          <ul className="divide-y divide-white/10">{visible.map((item) => <li key={item.path} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <button type="button" onClick={() => openHistory(item.path)} className="text-sm text-[#3FC8E8] break-all text-left">{item.path}</button>
            <span className="text-xs text-white/50">{item.changes || 0} changes · {item.authors || 0} authors · +{item.insertions || 0} / −{item.deletions || 0}</span>
          </li>)}</ul>
        </>}
        {view === "contributors" && <ul className="divide-y divide-white/10">{visible.map((item, index) => <li key={`${item.author}-${index}`} className="py-3 flex flex-wrap justify-between gap-2">
          <div><p className="text-sm">{item.author || "Unknown author"}</p><p className="text-xs text-white/40 break-all">{item.email}</p></div>
          <p className="text-xs text-white/50">{item.commits || 0} commits · {item.stats_available === false ? "Change counts unavailable" : `+${item.insertions || 0} / −${item.deletions || 0}`}</p>
        </li>)}</ul>}
        {view === "complexity" && <div className="space-y-3" data-testid="timeline-churn">
          <p className="text-xs text-white/50">Code churn counts lines added and removed. It does not measure code complexity.</p>
          {items.map((item, index) => <div key={index} className="space-y-1">
            <div className="flex flex-wrap justify-between gap-2 text-xs text-white/65"><span>{date(item.from)} — {date(item.to)}</span><span>{item.stats_available === false ? "Churn unavailable" : `${item.churn || 0} lines`} · {item.commits || 0} commits</span></div>
            {item.stats_available !== false && <div className="h-2 rounded bg-white/5" aria-hidden="true"><div className="h-2 rounded bg-[#3FC8E8]/60" style={{ width: `${100 * (item.churn || 0) / Math.max(1, ...items.map((entry) => entry.churn || 0))}%` }} /></div>}
          </div>)}
        </div>}
      </>}
  </section>;
}
