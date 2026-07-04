import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Loader2, Search, Brain, X, Plus, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { SkeletonGrid } from "../components/ui/skeleton";
import { EmptyState, ErrorState } from "../components/ui/state";

const SEV = { critical: "#FF3B30", high: "#FF9100", medium: "#FFB300", low: "#34C759", info: "#9CA3AF" };
const STATUS = { open: "#FFB300", in_progress: "#3FC8E8", resolved: "#34C759", wont_fix: "#9CA3AF" };
const CATEGORIES = ["", "architecture", "security", "performance", "testing", "documentation", "refactoring", "tech_debt", "note"];

function Card({ m, onClick }) {
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
        <span className="text-[9px] mono text-white/40 ml-auto">{pending ? <Loader2 size={10} className="animate-spin" aria-label="Saving" /> : m.category}</span>
      </div>
      <div className="text-sm text-white truncate" style={{ fontFamily: "Chivo" }}>{m.title}</div>
      {m.file_path && <div className="text-[10px] mono text-white/40 truncate mt-0.5">{m.file_path}</div>}
    </button>
  );
}

export default function MemoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ repo_id: "", category: "", severity: "", status: "" });
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ repo_id: "", category: "note", title: "", description: "", severity: "medium", file_path: "" });
  const firstFieldRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
      const url = search.trim() ? `/memory/search?q=${encodeURIComponent(search.trim())}` : `/memory?${params.toString()}`;
      const [r, s] = await Promise.all([
        api.get(url),
        api.get(`/memory/stats${filters.repo_id ? `?repo_id=${filters.repo_id}` : ""}`),
      ]);
      setItems(r.data); setStats(s.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to load memory.");
    } finally {
      setLoading(false);
    }
  }, [filters, search]);

  useEffect(() => {
    api.get("/repos").then((r) => setRepos(r.data)).catch(() => toast.error("Failed to load repository list"));
  }, []);
  useEffect(() => { load(); }, [JSON.stringify(filters)]); // eslint-disable-line react-hooks/exhaustive-deps

  // Escape closes whichever overlay is open (drawer takes precedence since
  // it can be opened from within the create flow's resulting card).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (selected) setSelected(null);
      else if (showCreate) setShowCreate(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, showCreate]);

  useEffect(() => {
    if (showCreate) firstFieldRef.current?.focus();
  }, [showCreate]);

  // Optimistic status update: the badge flips immediately; reverts + toasts
  // on failure.
  const update = async (mid, patch) => {
    const snapshot = items;
    setItems((its) => its.map((it) => (it.id === mid ? { ...it, ...patch } : it)));
    setSelected((s) => (s && s.id === mid ? { ...s, ...patch } : s));
    try {
      await api.patch(`/memory/${mid}`, patch);
      toast.success("Updated");
    } catch (err) {
      setItems(snapshot); // rollback
      setSelected((s) => (s && s.id === mid ? snapshot.find((x) => x.id === mid) || s : s));
      toast.error(err?.response?.data?.detail || "Failed to update memory");
    }
  };

  // Optimistic delete: card disappears immediately; restored on failure.
  const remove = async (mid) => {
    if (!window.confirm("Delete this memory?")) return;
    const snapshot = items;
    setItems((its) => its.filter((it) => it.id !== mid));
    setSelected(null);
    try {
      await api.delete(`/memory/${mid}`);
      toast.success("Deleted");
    } catch (err) {
      setItems(snapshot); // rollback
      toast.error(err?.response?.data?.detail || "Failed to delete memory");
    }
  };

  // Optimistic create: a placeholder card appears in the grid the instant
  // the form is submitted; it's swapped for the real record on success, or
  // removed with an error toast on failure.
  const createMemory = async (e) => {
    e.preventDefault();
    if (!draft.repo_id) { toast.error("Pick a repository"); return; }
    if (!draft.title.trim()) { toast.error("Title is required"); return; }
    setCreating(true);
    const placeholder = {
      id: `optimistic-${Date.now()}`,
      ...draft,
      file_path: draft.file_path.trim() || null,
      tags: [],
      status: "open",
    };
    setItems((its) => [placeholder, ...its]);
    setShowCreate(false);
    try {
      const r = await api.post("/memory", { ...draft, file_path: draft.file_path.trim() || null, tags: [] });
      setItems((its) => its.map((it) => (it.id === placeholder.id ? r.data : it)));
      toast.success("Memory added");
      setDraft({ repo_id: draft.repo_id, category: "note", title: "", description: "", severity: "medium", file_path: "" });
      // Refresh stats to reflect the new item's counts.
      api.get(`/memory/stats${filters.repo_id ? `?repo_id=${filters.repo_id}` : ""}`).then((s) => setStats(s.data)).catch(() => {});
    } catch (err) {
      setItems((its) => its.filter((it) => it.id !== placeholder.id)); // rollback
      toast.error(err?.response?.data?.detail || "Failed to add memory");
      setShowCreate(true); // let the user fix and resubmit without retyping
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-5" data-testid="memory-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// engineering memory"}</div>
          <h1 className="text-3xl font-semibold tracking-tighter mt-1 flex items-center gap-2" style={{ fontFamily: "Chivo" }}><Brain size={24} className="text-[#3FC8E8]" aria-hidden="true" /> Engineering Memory</h1>
          <p className="text-sm text-white/50 mt-1">Persistent knowledge across reviews — findings, debt, decisions, and your own notes.</p>
        </div>
        <button
          data-testid="memory-new-button"
          onClick={() => { setDraft((d) => ({ ...d, repo_id: d.repo_id || repos[0]?.id || "" })); setShowCreate(true); }}
          className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2"
        >
          <Plus size={14} aria-hidden="true" /> New memory
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 animate-in fade-in duration-200">
          {[
            ["Total", stats.total, "#fff"],
            ["Open", stats.by_status?.open || 0, "#FFB300"],
            ["In progress", stats.by_status?.in_progress || 0, "#3FC8E8"],
            ["Resolved", stats.by_status?.resolved || 0, "#34C759"],
            ["Critical+High", (stats.by_severity?.critical || 0) + (stats.by_severity?.high || 0), "#FF3B30"],
          ].map(([l, v, c]) => (
            <div key={l} className="glass-panel border border-white/10 rounded-xl p-3" data-testid={`memory-stat-${l.toLowerCase().replace(/\W/g, "-")}`}>
              <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">{l}</div>
              <div className="text-2xl font-semibold mt-1" style={{ color: c, fontFamily: "Chivo" }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      <div className="glass-panel border border-white/10 rounded-xl p-3 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1.5 flex-1 min-w-[200px] focus-within:border-[#3FC8E8]">
          <Search size={12} className="text-white/40" aria-hidden="true" />
          <label htmlFor="memory-search-input" className="sr-only">Semantic search</label>
          <input id="memory-search-input" data-testid="memory-search" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} placeholder="Semantic search…" className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30" />
        </div>
        <label htmlFor="memory-filter-repo" className="sr-only">Filter by repository</label>
        <select id="memory-filter-repo" data-testid="memory-filter-repo" value={filters.repo_id} onChange={(e) => setFilters({ ...filters, repo_id: e.target.value })} className="glass-panel-soft border border-white/10 rounded-xl text-xs mono px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
          <option value="">All repos</option>
          {repos.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        {[["category", CATEGORIES], ["severity", ["", "critical", "high", "medium", "low", "info"]], ["status", ["", "open", "in_progress", "resolved", "wont_fix"]]].map(([k, opts]) => (
          <select key={k} aria-label={`Filter by ${k}`} data-testid={`memory-filter-${k}`} value={filters[k]} onChange={(e) => setFilters({ ...filters, [k]: e.target.value })} className="glass-panel-soft border border-white/10 rounded-xl text-xs mono px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
            {opts.map((o) => <option key={o} value={o}>{o || `All ${k}`}</option>)}
          </select>
        ))}
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} testId="memory-error" />
      ) : loading ? (
        <SkeletonGrid cols={3} count={6} cardClassName="h-24" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Brain}
          title="No memories yet."
          subtitle="Run a code review to auto-populate this board, or add a note manually."
          action={{ label: "New memory", onClick: () => setShowCreate(true) }}
          testId="memory-empty"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="memory-grid">
          {items.map((m) => <Card key={m.id} m={m} onClick={() => !String(m.id).startsWith("optimistic-") && setSelected(m)} />)}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 animate-in fade-in duration-150" onClick={() => setShowCreate(false)} data-testid="memory-create-modal">
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={createMemory}
            role="dialog"
            aria-modal="true"
            aria-labelledby="memory-create-title"
            className="w-full max-w-md glass-panel-soft border border-white/10 rounded-xl p-5 space-y-3 animate-in fade-in zoom-in-95 duration-150"
          >
            <div className="flex items-center justify-between">
              <h2 id="memory-create-title" className="text-lg tracking-tight font-medium" style={{ fontFamily: "Chivo" }}>New memory</h2>
              <button type="button" onClick={() => setShowCreate(false)} aria-label="Close" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm"><X size={16} aria-hidden="true" /></button>
            </div>
            <div>
              <label htmlFor="memory-create-repo" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Repository</label>
              <select ref={firstFieldRef} id="memory-create-repo" data-testid="memory-create-repo" required value={draft.repo_id} onChange={(e) => setDraft({ ...draft, repo_id: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
                <option value="" disabled>Select a repository…</option>
                {repos.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="memory-create-title-input" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Title</label>
              <input id="memory-create-title-input" data-testid="memory-create-title" required value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8]" placeholder="e.g. Revisit retry logic in ingestion pipeline" />
            </div>
            <div>
              <label htmlFor="memory-create-desc" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Description</label>
              <textarea id="memory-create-desc" data-testid="memory-create-description" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} rows={3} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8] resize-none" placeholder="Optional context…" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="memory-create-cat" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Category</label>
                <select id="memory-create-cat" data-testid="memory-create-category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
                  {CATEGORIES.filter(Boolean).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="memory-create-sev" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Severity</label>
                <select id="memory-create-sev" data-testid="memory-create-severity" value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
                  {["critical", "high", "medium", "low", "info"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="memory-create-path" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">File path (optional)</label>
              <input id="memory-create-path" data-testid="memory-create-filepath" value={draft.file_path} onChange={(e) => setDraft({ ...draft, file_path: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8] mono" placeholder="src/services/foo.py" />
            </div>
            <button data-testid="memory-create-submit" type="submit" disabled={creating} className="w-full bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black rounded-lg py-2 text-sm flex items-center justify-center gap-2 mt-2 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2">
              {creating ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />} Add memory
            </button>
          </form>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex justify-end animate-in fade-in duration-150" onClick={() => setSelected(null)} data-testid="memory-drawer">
          <div
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="memory-drawer-title"
            className="w-full max-w-md glass-panel-soft border-l border-white/10 h-full overflow-auto p-5 animate-in slide-in-from-right duration-200"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">{selected.category}</div>
                <h2 id="memory-drawer-title" className="text-lg tracking-tight font-medium mt-1" style={{ fontFamily: "Chivo" }}>{selected.title}</h2>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Close" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm"><X size={16} aria-hidden="true" /></button>
            </div>
            <p className="text-sm text-white/70 whitespace-pre-wrap leading-relaxed">{selected.description || "No description."}</p>
            {selected.file_path && <div className="text-[11px] mono text-white/50 mt-3">{selected.file_path}{selected.symbol ? ` · ${selected.symbol}` : ""}</div>}
            {(selected.file_path || selected.symbol) && (
              <button
                data-testid="memory-open-workspace"
                onClick={() => {
                  const params = new URLSearchParams();
                  if (selected.file_path) params.set("file", selected.file_path);
                  if (selected.symbol) params.set("symbol", selected.symbol);
                  navigate(`/repositories/${selected.repo_id}?${params.toString()}`);
                }}
                className="mt-3 text-xs mono flex items-center gap-1.5 text-[#3FC8E8] hover:text-white border border-[#3FC8E8]/40 hover:bg-[#3FC8E8]/10 px-2.5 py-1.5 rounded-sm w-fit transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
              >
                <ExternalLink size={12} aria-hidden="true" /> Open in workspace
              </button>
            )}
            {selected.tags?.length > 0 && <div className="flex gap-1 flex-wrap mt-3">{selected.tags.map((t) => <span key={t} className="text-[10px] mono bg-white/5 px-1.5 py-0.5 rounded-sm text-white/60">{t}</span>)}</div>}
            <div className="mt-5 space-y-2">
              <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Status</div>
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Change status">
                {["open", "in_progress", "resolved", "wont_fix"].map((s) => (
                  <button key={s} data-testid={`memory-status-${s}`} aria-pressed={selected.status === s} onClick={() => update(selected.id, { status: s })} className={`text-xs mono uppercase tracking-[0.16em] px-2 py-1 rounded-sm border transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] ${selected.status === s ? "border-[#3FC8E8] text-[#3FC8E8]" : "border-white/10 text-white/60 hover:border-white/30"}`}>{s.replace("_", " ")}</button>
                ))}
              </div>
            </div>
            <button data-testid="memory-delete" onClick={() => remove(selected.id)} className="mt-6 text-xs text-[#FF3B30] hover:text-white border border-[#FF3B30]/40 hover:bg-[#FF3B30] px-3 py-1.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FF3B30]">Delete memory</button>
          </div>
        </div>
      )}
    </div>
  );
}
