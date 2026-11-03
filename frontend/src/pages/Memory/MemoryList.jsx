import BrainIcon from "../../assets/icons/brain.svg?react";
import { SkeletonList } from "../../components/Skeleton";
import { EmptyState, ErrorState } from "../../components/EmptyState";
import MemoryCard from "./MemoryCard";

export default function MemoryList({ items, repos, loading, error, onRetry, onSelect, onUpdate, updating, onNew, canCreate, filtered, onReset }) {
  if (error) return <ErrorState message={error} onRetry={onRetry} testId="memory-error" />;
  if (loading) return <SkeletonList rows={4} rowClassName="h-28" />;
  if (!items.length) return <EmptyState icon={BrainIcon} title={filtered ? "No matching saved items" : "No saved context yet"} subtitle={filtered ? "Try another search or clear the filters for this repository." : "Save findings from a code review, or add a decision or note you want to revisit."} action={filtered ? { label: "Clear filters", onClick: onReset } : canCreate ? { label: "Add your first memory", onClick: onNew } : undefined} testId="memory-empty" />;
  const names = new Map(repos.map(repo => [repo.id, repo.name]));
  return <ul className="memory-list" data-testid="memory-grid">{items.map(memory => <MemoryCard key={memory.id} m={memory} repoName={names.get(memory.repo_id)} onClick={() => onSelect(memory)} onUpdate={onUpdate} updating={updating} />)}</ul>;
}
