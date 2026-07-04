import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Trash2, GitBranch, Upload, FolderOpen, RefreshCw } from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { SkeletonList } from "../components/ui/skeleton";
import { EmptyState, ErrorState } from "../components/ui/state";

const statusColor = {
  queued: "text-white/50",
  cloning: "text-[#FFB300]",
  parsing: "text-[#FFB300]",
  embedding: "text-[#FFB300]",
  ready: "text-[#34C759]",
  failed: "text-[#FF3B30]",
};

export default function Repositories() {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const inFlight = useRef(new Set()); // repo ids with an optimistic action pending

  const load = useCallback(async () => {
    const r = await api.get("/repos");
    setRepos(r.data);
    setError(null);
  }, []);

  useEffect(() => {
    setLoading(true);
    load().catch((e) => setError(e?.response?.data?.detail || "Failed to load repositories.")).finally(() => setLoading(false));
  }, [load]);

  // Poll for in-progress ingestions
  useEffect(() => {
    const inProgress = repos.some((r) => !["ready", "failed"].includes(r.status));
    if (!inProgress) return;
    const t = setInterval(() => load().catch(() => {}), 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repos.map((r) => r.status).join(",")]);

  const addGithub = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api.post("/repos/github", { url: url.trim(), branch: branch.trim() || null });
      toast.success("Repository queued for ingestion");
      setUrl(""); setBranch("");
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to add repository");
    } finally { setBusy(false); }
  };

  const uploadZip = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("name", file.name.replace(/\.zip$/i, ""));
      await api.post("/repos/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("ZIP uploaded — ingestion started");
      setFile(null);
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally { setBusy(false); }
  };

  // Optimistic delete: the row disappears immediately; if the backend call
  // fails, it's put back and the user is told why.
  const remove = async (id) => {
    if (!window.confirm("Delete this repository and all its graph/vector data?")) return;
    if (inFlight.current.has(id)) return;
    inFlight.current.add(id);
    const snapshot = repos;
    setRepos((rs) => rs.filter((r) => r.id !== id));
    try {
      await api.delete(`/repos/${id}`);
      toast.success("Repository deleted");
    } catch (err) {
      setRepos(snapshot); // rollback
      toast.error(err?.response?.data?.detail || "Failed to delete repository");
    } finally {
      inFlight.current.delete(id);
    }
  };

  // Optimistic reingest: flips the row to "queued" immediately so the
  // progress bar appears at once instead of waiting a round trip.
  const reingest = async (id) => {
    if (inFlight.current.has(id)) return;
    inFlight.current.add(id);
    const snapshot = repos;
    setRepos((rs) => rs.map((r) => (r.id === id ? { ...r, status: "queued", progress: 0, message: "Queued for reingestion…" } : r)));
    try {
      await api.post(`/repos/${id}/reingest`);
      toast.success("Reingestion started");
      await load();
    } catch (err) {
      setRepos(snapshot); // rollback
      toast.error(err?.response?.data?.detail || "Failed to start reingestion");
    } finally {
      inFlight.current.delete(id);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="repos-root">
      <div>
        <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// repositories"}</div>
        <h1 className="text-3xl font-semibold tracking-tighter mt-1" style={{ fontFamily: "Chivo" }}>Repositories</h1>
        <p className="text-sm text-white/50 mt-2">Connect a GitHub repo or upload a ZIP. Each one is parsed with tree-sitter, indexed into a knowledge graph, and made queryable.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <form onSubmit={addGithub} className="glass-panel border border-white/10 rounded-xl p-5" data-testid="add-github-form">
          <div className="flex items-center gap-2 mb-3">
            <FaGithub size={18} className="text-white/70" aria-hidden="true" />
            <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Add from GitHub</h2>
          </div>
          <div className="space-y-3">
            <div>
              <Label htmlFor="github-url" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Repository URL</Label>
              <Input
                id="github-url"
                data-testid="github-url-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo.git"
                className="glass-panel-soft border-white/10 mono text-xs rounded-xl focus-visible:border-[#3FC8E8] focus-visible:ring-1 focus-visible:ring-[#3FC8E8] mt-1"
              />
            </div>
            <div>
              <Label htmlFor="github-branch" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Branch (optional)</Label>
              <Input
                id="github-branch"
                data-testid="github-branch-input"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
                className="glass-panel-soft border-white/10 mono text-xs rounded-xl focus-visible:border-[#3FC8E8] focus-visible:ring-1 focus-visible:ring-[#3FC8E8] mt-1"
              />
            </div>
            <Button data-testid="add-github-button" type="submit" disabled={busy} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black">
              {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : "Clone & ingest"}
            </Button>
          </div>
        </form>

        <div className="glass-panel border border-white/10 rounded-xl p-5" data-testid="upload-zip-card">
          <div className="flex items-center gap-2 mb-3">
            <Upload size={16} className="text-white/70" aria-hidden="true" />
            <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Upload ZIP</h2>
          </div>
          <label className="block border-2 border-dashed border-white/10 hover:border-white/30 transition-colors duration-150 rounded-sm p-6 text-center cursor-pointer focus-within:border-[#3FC8E8]">
            <input
              data-testid="zip-file-input"
              type="file"
              accept=".zip"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              aria-label="Choose a ZIP file to upload"
            />
            <FolderOpen size={22} className="mx-auto text-white/40 mb-2" aria-hidden="true" />
            <div className="text-xs text-white/60">{file ? file.name : "Click or drop a .zip up to 200 MB"}</div>
          </label>
          <Button data-testid="upload-zip-button" onClick={uploadZip} disabled={!file || busy} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black mt-3">
            {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : "Upload & ingest"}
          </Button>
        </div>
      </div>

      <div className="glass-panel border border-white/10 rounded-xl" data-testid="repos-list">
        <div className="px-5 py-3 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Your repositories</h2>
          <span className="text-[10px] mono text-white/40 uppercase tracking-[0.18em]">{repos.length} total</span>
        </div>
        {error ? (
          <ErrorState message={error} onRetry={() => { setLoading(true); load().catch((e) => setError(e?.response?.data?.detail || "Failed to load repositories.")).finally(() => setLoading(false)); }} testId="repos-error" />
        ) : loading ? (
          <SkeletonList rows={4} rowClassName="h-14" />
        ) : repos.length === 0 ? (
          <EmptyState title="No repositories yet." subtitle="Add one above via GitHub URL or ZIP upload to get started." testId="repos-empty" />
        ) : (
          <ul className="divide-y divide-white/10">
            {repos.map((r) => (
              <li key={r.id} className="px-5 py-4 hover:bg-white/[0.02] transition-colors duration-150 animate-in fade-in duration-200" data-testid={`repo-item-${r.id}`}>
                <div className="flex items-start gap-4">
                  <div className="w-9 h-9 rounded-sm bg-white/5 flex items-center justify-center mt-0.5">
                    {r.source === "github" ? <FaGithub size={16} className="text-white/70" aria-hidden="true" /> : <FolderOpen size={16} className="text-white/70" aria-hidden="true" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <Link to={`/repositories/${r.id}`} data-testid={`repo-open-${r.id}`} className="text-white font-medium text-sm hover:text-[#3FC8E8] transition-colors truncate focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm">{r.name}</Link>
                      <span className={`text-[10px] uppercase tracking-[0.18em] mono ${statusColor[r.status] || "text-white/50"}`}>{r.status}</span>
                      {r.branch && <span className="text-[10px] mono text-white/40 flex items-center gap-1"><GitBranch size={10} aria-hidden="true" />{r.branch}</span>}
                    </div>
                    {r.source_url && <div className="text-[11px] mono text-white/40 mt-0.5 truncate">{r.source_url}</div>}
                    {r.status !== "ready" && r.status !== "failed" && (
                      <div className="mt-2 h-1 bg-white/5 rounded-sm overflow-hidden">
                        <div className="h-full bg-[#3FC8E8] transition-all duration-300" style={{ width: `${r.progress || 0}%` }} />
                      </div>
                    )}
                    {r.message && <div className="text-[11px] text-white/40 mt-1">{r.message}</div>}
                    {r.status === "ready" && (
                      <div className="flex flex-wrap gap-3 mt-2 text-[11px] mono text-white/50">
                        <span>{r.stats?.files || 0} files</span>
                        <span>{r.stats?.loc || 0} loc</span>
                        <span>{r.stats?.nodes || 0} nodes</span>
                        <span>{r.stats?.edges || 0} edges</span>
                        <span>{r.stats?.chunks || 0} chunks</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button data-testid={`repo-reingest-${r.id}`} onClick={() => reingest(r.id)} aria-label={`Reingest ${r.name}`} title="Reingest" className="p-2 hover:bg-white/5 rounded-sm text-white/50 hover:text-white transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"><RefreshCw size={14} aria-hidden="true" /></button>
                    <button data-testid={`repo-delete-${r.id}`} onClick={() => remove(r.id)} aria-label={`Delete ${r.name}`} title="Delete" className="p-2 hover:bg-white/5 rounded-sm text-white/50 hover:text-[#FF3B30] transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FF3B30]"><Trash2 size={14} aria-hidden="true" /></button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
