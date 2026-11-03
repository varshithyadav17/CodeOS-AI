import SearchIcon from "../../assets/icons/search.svg?react";

const CATEGORIES = ["", "architecture", "security", "performance", "testing", "documentation", "refactoring", "tech_debt", "decision", "note"];
const label = value => value === "wont_fix" ? "Won’t fix" : value.replaceAll("_", " ");

export default function SearchMemory({ search, setSearch, onSearchEnter, repos, filters, setFilters }) {
  return <div className="memory-filters">
    <div className="memory-project-picker"><label htmlFor="memory-filter-repo">Repository</label><select id="memory-filter-repo" data-testid="memory-filter-repo" value={filters.repo_id} onChange={event => setFilters({ ...filters, repo_id: event.target.value })}><option value="">All repositories</option>{repos.map(repo => <option key={repo.id} value={repo.id}>{repo.name}</option>)}</select></div>
    <div className="memory-search-field"><SearchIcon width={15} height={15} aria-hidden="true" /><label htmlFor="memory-search-input" className="sr-only">Search memory</label><input id="memory-search-input" data-testid="memory-search" value={search} maxLength={1000} onChange={event => setSearch(event.target.value)} onKeyDown={event => event.key === "Enter" && onSearchEnter()} placeholder="Search findings, files, or decisions" /></div>
    <div className="memory-secondary-filters">{[["category", CATEGORIES], ["severity", ["", "critical", "high", "medium", "low", "info"]], ["status", ["", "open", "in_progress", "resolved", "wont_fix"]]].map(([key, values]) => <select key={key} aria-label={`Filter by ${key}`} data-testid={`memory-filter-${key}`} value={filters[key]} onChange={event => setFilters({ ...filters, [key]: event.target.value })}>{values.map(value => <option key={value} value={value}>{value ? label(value) : `All ${key === "category" ? "categories" : key === "severity" ? "priorities" : "statuses"}`}</option>)}</select>)}</div>
  </div>;
}

export { CATEGORIES };
