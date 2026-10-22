import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import BrainIcon from "../../assets/icons/brain.svg?react";
import PlusIcon from "../../assets/icons/plus.svg?react";
import { toast } from "sonner";
import SearchMemory from "./SearchMemory";
import MemoryList from "./MemoryList";
import MemoryCreateForm from "./MemoryCreateForm";
import MemoryDetail from "./MemoryDetail";

export default function MemoryPage() {
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
      if (search.trim()) params.set("q", search.trim());
      const url = `${search.trim() ? "/memory/search" : "/memory"}?${params.toString()}`;
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
  useEffect(() => {
    const timer = setTimeout(load, search.trim() ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

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
      await load();
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
      await load();
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
          <h1 className="text-3xl font-semibold tracking-tighter mt-1 flex items-center gap-2" style={{ fontFamily: "Chivo" }}><BrainIcon width={24} height={24} className="text-[#3FC8E8]" aria-hidden="true" /> Engineering Memory</h1>
          <p className="text-sm text-white/50 mt-1">Persistent knowledge across reviews — findings, debt, decisions, and your own notes.</p>
        </div>
        <button
          data-testid="memory-new-button"
          onClick={() => { setDraft((d) => ({ ...d, repo_id: d.repo_id || repos[0]?.id || "" })); setShowCreate(true); }}
          className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black px-3 py-2 rounded-lg text-sm flex items-center gap-1.5 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2"
        >
          <PlusIcon width={14} height={14} aria-hidden="true" /> New memory
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

      <SearchMemory search={search} setSearch={setSearch} onSearchEnter={load} repos={repos} filters={filters} setFilters={setFilters} />

      <MemoryList items={items} loading={loading} error={error} onRetry={load} onSelect={setSelected} onNew={() => setShowCreate(true)} />

      {showCreate && (
        <MemoryCreateForm
          repos={repos}
          draft={draft}
          setDraft={setDraft}
          creating={creating}
          onSubmit={createMemory}
          onClose={() => setShowCreate(false)}
          firstFieldRef={firstFieldRef}
        />
      )}

      {selected && (
        <MemoryDetail selected={selected} onClose={() => setSelected(null)} onUpdate={update} onDelete={remove} />
      )}
    </div>
  );
}
