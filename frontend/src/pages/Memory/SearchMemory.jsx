import SearchIcon from "../../assets/icons/search.svg?react";

const CATEGORIES = ["", "architecture", "security", "performance", "testing", "documentation", "refactoring", "tech_debt", "note"];

/** Search box + repo/category/severity/status filter row above the memory grid. */
export default function SearchMemory({ search, setSearch, onSearchEnter, repos, filters, setFilters }) {
  return (
    <div className="glass-panel border border-white/10 rounded-xl p-3 flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1.5 flex-1 min-w-[200px] focus-within:border-[#3FC8E8]">
        <SearchIcon width={12} height={12} className="text-white/40" aria-hidden="true" />
        <label htmlFor="memory-search-input" className="sr-only">Search memory</label>
        <input id="memory-search-input" data-testid="memory-search" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && onSearchEnter()} placeholder="Search memory…" className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30" />
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
  );
}

export { CATEGORIES };
