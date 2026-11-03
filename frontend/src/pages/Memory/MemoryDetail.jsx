import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import XIcon from "../../assets/icons/x.svg?react";
import ExternalLinkIcon from "../../assets/icons/external-link.svg?react";
import { useFetch } from "../../hooks/useFetch";
import { memoryChatDraft } from "../../lib/engineeringMemory";

export default function MemoryDetail({ selected, repo, onClose, onUpdate, updating, onDelete }) {
  const navigate = useNavigate();
  const dialogRef = useRef(null);
  const review = useFetch(selected.review_id ? `/reviews/${selected.review_id}` : null);
  const finding = review.data?.agents?.flatMap(agent => agent.findings || []).find(item => item.id === selected.finding_id);
  const ready = repo?.status === "ready";
  useEffect(() => {
    const previousFocus = document.activeElement;
    dialogRef.current?.querySelector("button")?.focus();
    return () => previousFocus?.focus();
  }, []);
  const trapFocus = event => {
    if (event.key !== "Tab") return;
    const focusable = Array.from(dialogRef.current.querySelectorAll("button:not(:disabled), a[href], select:not(:disabled)"));
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  const openWorkspace = () => {
    const params = new URLSearchParams();
    if (selected.file_path) params.set("file", selected.file_path);
    if (selected.symbol) params.set("symbol", selected.symbol);
    navigate(`/repositories/${selected.repo_id}${params.size ? `?${params}` : ""}`);
  };
  const statuses = { open: "Open", in_progress: "In progress", resolved: "Resolved", wont_fix: "Won’t fix" };
  return <div className="memory-drawer-backdrop" onClick={onClose} data-testid="memory-drawer">
    <div ref={dialogRef} onClick={event => event.stopPropagation()} onKeyDown={trapFocus} role="dialog" aria-modal="true" aria-labelledby="memory-drawer-title" className="memory-detail">
      <header className="memory-detail-heading"><div><span className="workspace-eyebrow">{repo?.name || "Repository"} · {selected.category.replaceAll("_", " ")}</span><h2 id="memory-drawer-title">{selected.title}</h2></div><button onClick={onClose} aria-label="Close"><XIcon width={18} height={18} aria-hidden="true" /></button></header>
      <div className="memory-detail-origin">{selected.source === "review" ? "Saved from a code review" : "Added by you"}{selected.updated_at && <> · Updated {new Date(selected.updated_at).toLocaleDateString()}</>}</div>
      <p className="memory-detail-description">{selected.description || "No description added."}</p>
      {selected.file_path && <div className="memory-detail-file"><span className="workspace-eyebrow">Source location</span><code>{selected.file_path}{finding?.line ? `:${finding.line}` : ""}{selected.symbol ? ` · ${selected.symbol}` : ""}</code></div>}
      {review.loading && <p className="workspace-muted">Loading original review…</p>}
      {finding?.recommendation && <section className="memory-recommendation" data-testid="memory-recommendation"><span className="workspace-eyebrow">From the original review</span><h3>Suggested next step</h3><p>{finding.recommendation}</p></section>}
      {review.error && <p className="memory-inline-error">Original review unavailable. Your saved finding is still here. <button onClick={review.retry}>Retry</button></p>}
      <div className="memory-detail-actions"><button data-testid="memory-open-workspace" onClick={openWorkspace} className="memory-secondary-button"><ExternalLinkIcon width={13} height={13} aria-hidden="true" />{selected.file_path ? "Open source" : "Open repository"}</button><button data-testid="memory-check-ai" disabled={!ready || review.loading} className="workspace-primary" onClick={() => navigate(`/repositories/${selected.repo_id}`, { state: { memoryContext: { repo_id: selected.repo_id, prompt: memoryChatDraft(selected, finding?.recommendation) } } })}>Check with AI →</button></div>
      <p className="memory-draft-hint">{ready ? "Opens a chat draft for you to review and send. Saved findings are not automatically rechecked." : "The repository needs to finish indexing before you can check a finding with AI."}</p>
      {selected.tags?.length > 0 && <div className="memory-detail-tags">{selected.tags.map(tag => <span key={tag}>{tag.replaceAll("_", " ")}</span>)}</div>}
      <section className="memory-detail-status"><h3>Status</h3><div role="group" aria-label="Change status">{Object.entries(statuses).map(([status, label]) => <button key={status} data-testid={`memory-status-${status}`} aria-pressed={selected.status === status} disabled={updating} onClick={() => onUpdate(selected.id, { status })}>{label}</button>)}</div></section>
      <button data-testid="memory-delete" onClick={() => onDelete(selected.id)} disabled={updating} className="memory-delete">Delete memory</button>
    </div>
  </div>;
}
