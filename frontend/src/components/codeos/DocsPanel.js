import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api, API } from "../../lib/api";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { FileText, Loader2, Download, Copy, RefreshCw, Package, MessageSquareText } from "lucide-react";
import { useWorkspace } from "../../context/WorkspaceContext";
import Skeleton from "../ui/skeleton";
import { ErrorState } from "../ui/state";

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Wraps plain-string children that contain `term` in <mark>, and turns
 * substrings that exactly match a known repo file path into a clickable
 * jump-to-file button. Used across markdown element renderers so both
 * "jump to related code" and "highlight the selected file" work without
 * a remark plugin. */
function useTextTransformers(term, knownFilePaths, onSelectPath) {
  return useMemo(() => {
    const transform = (child, key) => {
      if (typeof child !== "string") return child;
      // Split on any known file path mention so it can become a link,
      // then further split the remainder on the highlighted term.
      const paths = knownFilePaths.size ? [...knownFilePaths].filter((p) => p.length > 3 && child.includes(p)) : [];
      if (paths.length === 0 && (!term || !child.includes(term))) return child;

      // Build one combined regex: known paths (as links) OR the search term (as <mark>).
      const pathPattern = paths.map(escapeRegExp).sort((a, b) => b.length - a.length).join("|");
      const parts = [];
      const pattern = new RegExp(`(${[pathPattern, term ? escapeRegExp(term) : null].filter(Boolean).join("|")})`, "g");
      let last = 0, m, i = 0;
      while ((m = pattern.exec(child)) !== null) {
        if (m.index > last) parts.push(child.slice(last, m.index));
        const hit = m[0];
        if (paths.includes(hit)) {
          parts.push(
            <button
              key={`${key}-p-${i++}`}
              onClick={(e) => { e.stopPropagation(); onSelectPath(hit); }}
              className="text-[#3FC8E8] hover:text-white underline decoration-dotted mono"
              data-testid="docs-file-link"
            >
              {hit}
            </button>
          );
        } else {
          parts.push(<mark key={`${key}-m-${i++}`} className="bg-[#3FC8E8]/25 text-white rounded-sm px-0.5">{hit}</mark>);
        }
        last = pattern.lastIndex;
      }
      if (last < child.length) parts.push(child.slice(last));
      return <Fragment key={key}>{parts}</Fragment>;
    };
    return {
      p: ({ children, ...p }) => <p {...p}>{(Array.isArray(children) ? children : [children]).map((c, i) => transform(c, i))}</p>,
      li: ({ children, ...p }) => <li {...p}>{(Array.isArray(children) ? children : [children]).map((c, i) => transform(c, i))}</li>,
      code: ({ children, ...p }) => <code {...p}>{(Array.isArray(children) ? children : [children]).map((c, i) => transform(c, i))}</code>,
      td: ({ children, ...p }) => <td {...p}>{(Array.isArray(children) ? children : [children]).map((c, i) => transform(c, i))}</td>,
    };
  }, [term, knownFilePaths, onSelectPath]);
}

export default function DocsPanel({ repoId, repoReady }) {
  const { selectedFilePath, knownFilePaths, selectFile, askInChat } = useWorkspace();
  const [types, setTypes] = useState([]);
  // Cache of generated docs keyed by doc_type — populated once from GET
  // /docs and updated in place on generate(), never re-fetched redundantly.
  const [docs, setDocs] = useState({});
  const [active, setActive] = useState("readme");
  const [busy, setBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const loadAll = useCallback((signal) => {
    setInitialLoading(true);
    setLoadError(null);
    Promise.all([
      api.get(`/repos/${repoId}/docs/types`, { signal }),
      api.get(`/repos/${repoId}/docs`, { signal }),
    ])
      .then(([t, d]) => {
        setTypes(t.data);
        const map = {};
        d.data.forEach((x) => { map[x.doc_type] = x; });
        setDocs(map);
      })
      .catch((e) => {
        if (signal?.aborted || e.code === "ERR_CANCELED") return;
        setLoadError(e?.response?.data?.detail || "Failed to load documentation.");
      })
      .finally(() => { if (!signal?.aborted) setInitialLoading(false); });
  }, [repoId]);

  useEffect(() => {
    const controller = new AbortController();
    loadAll(controller.signal);
    return () => controller.abort();
  }, [loadAll]);

  // Cross-panel: when a file gets selected elsewhere in the workspace,
  // auto-switch to whichever *already generated* doc mentions it the most,
  // so "open documentation" from Files/Graph/Architecture actually lands
  // somewhere useful. We deliberately never call /docs/generate here — the
  // existing API only generates whole-repo docs (readme/architecture/api/…),
  // there's no per-file generation endpoint, and auto-firing an LLM call on
  // every click would be slow and costly. Regeneration stays an explicit
  // user action via the button below.
  useEffect(() => {
    if (!selectedFilePath) return;
    const entries = Object.entries(docs);
    if (entries.length === 0) return;
    let best = null, bestCount = 0;
    for (const [key, doc] of entries) {
      const count = (doc.content.match(new RegExp(escapeRegExp(selectedFilePath), "g")) || []).length;
      if (count > bestCount) { best = key; bestCount = count; }
    }
    if (best && best !== active) setActive(best);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFilePath, docs]);

  const generate = async (t) => {
    setBusy(true);
    try {
      const r = await api.post(`/repos/${repoId}/docs/generate`, { doc_type: t });
      setDocs((d) => ({ ...d, [t]: r.data }));
      toast.success(`Generated ${t}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to generate documentation");
    }
    setBusy(false);
  };

  const copy = () => { navigator.clipboard.writeText(docs[active]?.content || ""); toast.success("Copied"); };
  const dl = () => {
    const blob = new Blob([docs[active]?.content || ""], { type: "text/markdown" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${active}.md`; a.click();
  };
  const dlZip = async () => {
    setExporting(true);
    try {
      const url = `${API}/repos/${repoId}/docs/export`;
      // `credentials: 'include'` sends the HttpOnly auth cookie set by the
      // backend on login — no need to read the JWT from JS-land.
      const r = await fetch(url, { credentials: "include" });
      if (!r.ok) throw new Error(`Export failed (${r.status})`);
      const b = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = "docs.zip";
      a.click();
    } catch (e) {
      toast.error(e.message || "Failed to export documentation");
    } finally {
      setExporting(false);
    }
  };

  const current = docs[active];
  const mentionsSelected = selectedFilePath && current ? (current.content.match(new RegExp(escapeRegExp(selectedFilePath), "g")) || []).length : 0;
  const mdComponents = useTextTransformers(selectedFilePath, knownFilePaths, selectFile);

  if (initialLoading) {
    return (
      <div className="grid grid-cols-12 gap-3" data-testid="docs-panel-loading">
        <Skeleton className="col-span-3 h-[600px]" />
        <Skeleton className="col-span-9 h-[600px]" />
      </div>
    );
  }

  if (loadError) {
    return <ErrorState message={loadError} onRetry={() => loadAll()} testId="docs-panel-error" />;
  }

  return (
    <div className="grid grid-cols-12 gap-3" data-testid="docs-panel">
      <div className="col-span-3 glass-panel border border-white/10 rounded-xl">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] mono uppercase tracking-[0.18em] text-white/50">Doc types</div>
        <div className="max-h-[560px] overflow-auto" role="list">
          {types.map((t) => (
            <button key={t.key} data-testid={`docs-type-${t.key}`} onClick={() => setActive(t.key)} aria-current={active === t.key}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-white/5 border-l-2 transition-colors duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-[-1px] ${active === t.key ? "border-[#3FC8E8] bg-white/5 text-white" : "border-transparent text-white/70"}`}>
              <div className="flex items-center gap-2"><FileText size={11} aria-hidden="true" /><span className="capitalize">{t.key}</span>{docs[t.key] && <span className="ml-auto text-[9px] text-[#34C759]" aria-label="Generated">●</span>}</div>
            </button>
          ))}
        </div>
        <button data-testid="docs-export-zip" onClick={dlZip} disabled={exporting} className="w-full p-2 text-[11px] mono text-[#3FC8E8] hover:bg-white/5 border-t border-white/10 flex items-center justify-center gap-1 disabled:opacity-50 transition-colors duration-150">
          {exporting ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <Package size={11} aria-hidden="true" />} Export ZIP
        </button>
      </div>
      <div className="col-span-9 glass-panel border border-white/10 rounded-xl flex flex-col h-[600px]">
        <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium capitalize" style={{ fontFamily: "Chivo" }}>{active}</span>
          {selectedFilePath && (
            <span className="text-[10px] mono text-white/40" data-testid="docs-mention-count">
              {mentionsSelected > 0 ? `${mentionsSelected} mention${mentionsSelected === 1 ? "" : "s"} of ${selectedFilePath}` : `no mentions of ${selectedFilePath}`}
            </span>
          )}
          <span className="ml-auto flex gap-1.5">
            {selectedFilePath && mentionsSelected === 0 && current && (
              <button
                data-testid="docs-ask-about-file"
                onClick={() => askInChat(`Document what ${selectedFilePath} does and how it fits into the rest of the codebase.`)}
                className="border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 text-xs px-2 py-1 rounded-sm flex items-center gap-1"
              >
                <MessageSquareText size={11} /> Ask about this file
              </button>
            )}
            <button data-testid="docs-generate" disabled={!repoReady || busy} onClick={() => generate(active)} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black text-xs px-3 py-1 rounded-lg flex items-center gap-1 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2">
              {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={11} aria-hidden="true" />}{current ? "Regenerate" : "Generate"}
            </button>
            <button data-testid="docs-copy" disabled={!current} onClick={copy} aria-label="Copy documentation to clipboard" className="border border-white/10 hover:border-white/30 disabled:opacity-50 text-white/70 text-xs px-2 py-1 rounded-sm flex items-center gap-1 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"><Copy size={11} aria-hidden="true" /> Copy</button>
            <button data-testid="docs-download" disabled={!current} onClick={dl} aria-label="Download documentation as Markdown" className="border border-white/10 hover:border-white/30 disabled:opacity-50 text-white/70 text-xs px-2 py-1 rounded-sm flex items-center gap-1 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"><Download size={11} aria-hidden="true" /> .md</button>
          </span>
        </div>
        <div className="flex-1 overflow-auto p-5 prose prose-invert prose-sm max-w-none" data-testid="docs-preview" aria-live="polite" aria-busy={busy}>
          {busy ? <div className="text-white/40 flex items-center gap-2" role="status"><Loader2 size={14} className="animate-spin" aria-hidden="true" /> Generating with Gemini 2.5 Pro…</div> :
           current ? <div className="animate-in fade-in duration-200" key={active}><ReactMarkdown components={mdComponents}>{current.content}</ReactMarkdown></div> :
           <div className="text-white/40 text-sm" data-testid="docs-empty">No documentation yet. Click <span className="text-[#3FC8E8] mono">Generate</span>.</div>}
        </div>
      </div>
    </div>
  );
}
