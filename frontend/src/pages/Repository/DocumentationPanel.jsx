import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../../lib/api";
import { Button } from "../../components/ui/button";

const DOC_LABELS = { readme: "README", api: "API reference", architecture: "Architecture", modules: "Modules", setup: "Setup guide", developer: "Developer guide", structure: "Folder structure", database: "Database", dependency: "Dependencies", pipeline: "Data and AI pipeline" };

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function DocumentationPanel({ repoId }) {
  const [types, setTypes] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const active = documents.find((doc) => doc.doc_type === selected);

  const load = useCallback(async (signal) => {
    setLoading(true);
    setError("");
    try {
      const [available, saved] = await Promise.all([
        api.get(`/repos/${repoId}/docs/types`, { signal }),
        api.get(`/repos/${repoId}/docs`, { signal }),
      ]);
      setTypes(available.data);
      setDocuments(saved.data);
      setSelected((current) => current || available.data[0]?.key || "");
    } catch (err) {
      if (!signal?.aborted) setError(err.response?.data?.detail || "Could not load documentation. Try again.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    setError("");
    try {
      const { data } = await api.post(`/repos/${repoId}/docs/generate`, { doc_type: selected }, { timeout: 360000 });
      setDocuments((current) => [...current.filter((doc) => doc.doc_type !== data.doc_type), data]);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not generate this draft. Try again.");
    } finally { setGenerating(false); }
  };

  const exportAll = async () => {
    setExporting(true);
    setError("");
    try {
      const { data } = await api.get(`/repos/${repoId}/docs/export`, { responseType: "blob" });
      download(data, `codeos-${repoId}-docs.zip`);
    } catch { setError("Could not export documentation. Try again."); }
    finally { setExporting(false); }
  };

  return (
    <section className="glass-panel rounded-xl border border-white/10 p-4 sm:p-6 space-y-5" data-testid="documentation-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-lg font-semibold text-white">Repository documentation</h2><p className="text-sm text-white/50 mt-1">Generate and save Markdown from repository evidence. Review AI drafts before publishing.</p></div>
        <Button variant="outline" size="sm" onClick={exportAll} disabled={!documents.length || exporting} data-testid="docs-export">{exporting ? "Exporting…" : `Export all (${documents.length})`}</Button>
      </div>
      {error && <div role="alert" className="rounded-lg border border-red-400/25 bg-red-400/10 p-3 text-sm text-red-200"><p>{error}</p><button className="mt-2 underline" onClick={() => load()} disabled={loading || generating}>Refresh saved documents</button></div>}
      {loading ? <p role="status" className="text-sm text-white/50">Loading saved documentation…</p> : <>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-2 text-xs text-white/60">Document type
            <select className="rounded-lg border border-white/15 bg-[#141721] px-3 py-2 text-sm text-white min-w-0" data-testid="docs-type" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={generating}>
              {types.map((type) => <option key={type.key} value={type.key}>{DOC_LABELS[type.key] || type.label}{documents.some((doc) => doc.doc_type === type.key) ? " · Saved" : ""}</option>)}
            </select>
          </label>
          <Button onClick={generate} disabled={!selected || generating} data-testid="docs-generate">{generating ? "Generating…" : active ? "Regenerate draft" : "Generate draft"}</Button>
        </div>
        {generating && <p role="status" className="text-sm text-cyan-200">Reading repository evidence and drafting documentation…</p>}
        {active ? <>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs text-white/50">
            <span>Saved {new Date(active.updated_at).toLocaleString()}</span>
            <Button size="sm" variant="ghost" onClick={() => download(new Blob([active.content], { type: "text/markdown;charset=utf-8" }), `${selected}.md`)}>Download Markdown</Button>
          </div>
          <article className="documentation-markdown min-w-0 break-words" data-testid="docs-content"><ReactMarkdown skipHtml components={{ img: ({ alt }) => <span>{alt || "Image"}</span>, a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> }}>{active.content}</ReactMarkdown></article>
        </> : <div className="rounded-lg border border-dashed border-white/15 p-8 text-center text-sm text-white/50" data-testid="docs-empty">Choose a document type and generate your first draft.</div>}
      </>}
    </section>
  );
}
