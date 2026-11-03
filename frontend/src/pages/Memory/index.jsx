import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import PlusIcon from "../../assets/icons/plus.svg?react";
import { api } from "../../lib/api";
import { sortMemories } from "../../lib/engineeringMemory";
import { useFetch } from "../../hooks/useFetch";
import SearchMemory from "./SearchMemory";
import MemoryList from "./MemoryList";
import MemoryCreateForm from "./MemoryCreateForm";
import MemoryDetail from "./MemoryDetail";
import "../workspace.css";

const newDraft = (repo_id = "") => ({ repo_id, category: "note", title: "", description: "", severity: "medium", file_path: "" });

export default function MemoryPage() {
  const [params, setParams] = useSearchParams();
  const filters = { repo_id: params.get("repo") || "", category: params.get("category") || "", severity: params.get("severity") || "", status: params.get("status") || "" };
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [order, setOrder] = useState("priority");
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [draft, setDraft] = useState(newDraft);
  const firstFieldRef = useRef(null);
  const resultParams = new URLSearchParams({ limit: "200" });
  Object.entries(filters).forEach(([key, value]) => { if (value) resultParams.set(key, value); });
  if (query) resultParams.set("q", query);
  // Cancel superseded searches and repository scopes through useFetch.
  const results = useFetch(`${query ? "/memory/search" : "/memory"}?${resultParams}`);
  const statistics = useFetch(`/memory/stats${filters.repo_id ? `?repo_id=${encodeURIComponent(filters.repo_id)}` : ""}`);
  const repositories = useFetch("/repos");
  const items = results.data || [];
  const repos = repositories.data || [];
  const stats = statistics.loading ? null : statistics.data;
  const currentRepo = repos.find(repo => repo.id === filters.repo_id);
  const target = params.get("item");

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!target) { setSelected(null); return; }
    if (results.loading) return;
    setSelected(results.data?.find(memory => memory.id === target) || null);
  }, [target, results.data, results.loading]);

  const closeDetail = () => {
    setSelected(null);
    if (target) setParams(previous => { const next = new URLSearchParams(previous); next.delete("item"); return next; }, { replace: true });
  };
  const setFilters = nextFilters => {
    setSelected(null);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.delete("item");
      Object.entries(nextFilters).forEach(([key, value]) => {
        const name = key === "repo_id" ? "repo" : key;
        if (value) next.set(name, value); else next.delete(name);
      });
      return next;
    });
  };
  useEffect(() => {
    const onKey = event => {
      if (event.key !== "Escape") return;
      if (selected) closeDetail();
      else if (!creating) setShowCreate(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, creating, target]);
  useEffect(() => { if (showCreate) firstFieldRef.current?.focus(); }, [showCreate]);

  const refresh = () => { results.retry(); statistics.retry(); };
  const update = async (id, patch) => {
    if (updating) return;
    setUpdating(true);
    try {
      const response = await api.patch(`/memory/${id}`, patch);
      setSelected(previous => previous?.id === id ? response.data : previous);
      refresh();
      toast.success("Status updated");
    } catch (error) { toast.error(error?.response?.data?.detail || "Failed to update memory"); }
    finally { setUpdating(false); }
  };
  const remove = async id => {
    if (updating || !window.confirm("Delete this memory?")) return;
    setUpdating(true);
    try { await api.delete(`/memory/${id}`); closeDetail(); refresh(); toast.success("Memory deleted"); }
    catch (error) { toast.error(error?.response?.data?.detail || "Failed to delete memory"); }
    finally { setUpdating(false); }
  };
  const startCreate = () => { setDraft(newDraft(filters.repo_id || repos[0]?.id || "")); setShowCreate(true); };
  const createMemory = async event => {
    event.preventDefault();
    if (creating) return;
    if (!draft.repo_id || !draft.title.trim()) { toast.error("Choose a repository and enter a title"); return; }
    setCreating(true);
    try {
      await api.post("/memory", { ...draft, title: draft.title.trim(), file_path: draft.file_path.trim() || null, tags: [] });
      setShowCreate(false); refresh(); toast.success("Memory added");
    } catch (error) { toast.error(error?.response?.data?.detail || "Failed to add memory"); }
    finally { setCreating(false); }
  };
  const filtered = Boolean(search || filters.category || filters.severity || filters.status);
  const countTabs = [["", "All", stats?.total], ["open", "Open", stats?.by_status?.open], ["in_progress", "In progress", stats?.by_status?.in_progress], ["resolved", "Resolved", stats?.by_status?.resolved]];

  return <div className="workspace-page memory-page" data-testid="memory-page">
    <header className="workspace-page-heading"><div><h1>Engineering Memory</h1><p>Saved findings, decisions, and next steps. Keep the context with the code, then return to it when you need it.</p></div><button data-testid="memory-new-button" onClick={startCreate} disabled={!repos.length} className="workspace-primary"><PlusIcon width={14} height={14} aria-hidden="true" /> New memory</button></header>
    <SearchMemory search={search} setSearch={setSearch} onSearchEnter={() => setQuery(search.trim())} repos={repos} filters={filters} setFilters={setFilters} />
    {repositories.error && <p className="memory-inline-error" role="alert">Repository list unavailable. <button onClick={repositories.retry}>Retry</button></p>}
    <div className="memory-context"><div><span className="workspace-eyebrow">{currentRepo?.name || (filters.repo_id ? "Selected repository" : "Across your workspace")}</span><p>Saved context stays here until you update its status. Use “Check with AI” to revisit a finding against the indexed code.</p></div></div>
    {stats && <div className="memory-status-tabs" aria-label="Filter memory by status">{countTabs.map(([status, label, value]) => <button key={status} data-testid={`memory-stat-${status || "total"}`} aria-pressed={filters.status === status} onClick={() => setFilters({ ...filters, status })}>{label}<span>{value || 0}</span></button>)}</div>}
    {statistics.error && <p className="memory-inline-error" role="alert">Status counts unavailable. <button onClick={statistics.retry}>Retry</button></p>}
    <div className="memory-list-heading"><p>{results.loading ? "Loading saved context…" : `${items.length} ${items.length === 1 ? "item" : "items"}${filtered ? " match your filters" : " saved"}`}</p><label>Sort by <select data-testid="memory-sort" value={order} onChange={event => setOrder(event.target.value)}><option value="priority">Priority</option><option value="recent">Recently updated</option></select></label></div>
    {target && !results.loading && !results.error && !items.some(item => item.id === target) && <p className="memory-inline-error">This finding is no longer in these results. Clear the filters to look for it.</p>}
    <MemoryList items={sortMemories(items, order)} repos={repos} loading={results.loading} error={results.error} onRetry={results.retry} onSelect={item => setParams(previous => { const next = new URLSearchParams(previous); next.set("item", item.id); return next; })} onUpdate={update} updating={updating} onNew={startCreate} canCreate={Boolean(repos.length)} filtered={filtered} onReset={() => { setSearch(""); setQuery(""); setFilters({ ...filters, category: "", severity: "", status: "" }); }} />
    {items.length === 200 && <p className="workspace-muted mt-3">Showing up to 200 saved items. Narrow by repository, status, or search to find older work.</p>}
    {showCreate && <MemoryCreateForm repos={repos} draft={draft} setDraft={setDraft} creating={creating} onSubmit={createMemory} onClose={() => !creating && setShowCreate(false)} firstFieldRef={firstFieldRef} />}
    {selected && <MemoryDetail key={selected.id} selected={selected} repo={repos.find(repo => repo.id === selected.repo_id)} onClose={closeDetail} onUpdate={update} updating={updating} onDelete={remove} />}
  </div>;
}
