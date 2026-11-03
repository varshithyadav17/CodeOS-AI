import ArrowUpRight from "../../assets/icons/arrow-up-right.svg?react";

const statusLabels = { open: "Open", in_progress: "In progress", resolved: "Resolved", wont_fix: "Won’t fix" };

export default function MemoryCard({ m, repoName, onClick, onUpdate, updating }) {
  return <li className="memory-row">
    <button onClick={onClick} data-testid={`memory-${m.id}`} className="memory-row-main">
      <span className={`memory-severity-dot severity-${m.severity}`} aria-hidden="true" />
      <div className="memory-row-content">
        <div className="memory-row-meta"><span>{repoName || "Repository"}</span><span>·</span><span>{m.category.replaceAll("_", " ")}</span><span className="memory-source-label">{m.source === "review" ? "Review finding" : "Your note"}</span></div>
        <h3>{m.title}</h3>
        {m.description && <p>{m.description}</p>}
        <div className="memory-row-footer"><span className={`memory-severity-label severity-label-${m.severity}`}>{m.severity} priority</span>{m.file_path && <code>{m.file_path}</code>}</div>
      </div>
      <ArrowUpRight width={15} height={15} className="memory-row-arrow" aria-hidden="true" />
    </button>
    <div className="memory-row-status"><label htmlFor={`memory-status-${m.id}`} className="sr-only">Status for {m.title}</label><select id={`memory-status-${m.id}`} data-testid={`memory-quick-status-${m.id}`} value={m.status} disabled={updating} onChange={event => onUpdate(m.id, { status: event.target.value })}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
  </li>;
}
