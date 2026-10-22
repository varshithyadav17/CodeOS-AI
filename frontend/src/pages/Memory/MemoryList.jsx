import BrainIcon from "../../assets/icons/brain.svg?react";
import { SkeletonGrid } from "../../components/Skeleton";
import { EmptyState, ErrorState } from "../../components/EmptyState";
import MemoryCard from "./MemoryCard";

/** Loading/error/empty states + the memory grid itself. */
export default function MemoryList({ items, loading, error, onRetry, onSelect, onNew }) {
  if (error) return <ErrorState message={error} onRetry={onRetry} testId="memory-error" />;
  if (loading) return <SkeletonGrid cols={3} count={6} cardClassName="h-24" />;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={BrainIcon}
        title="No memories yet."
        subtitle="Run a code review to auto-populate this board, or add a note manually."
        action={{ label: "New memory", onClick: onNew }}
        testId="memory-empty"
      />
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="memory-grid">
      {items.map((m) => <MemoryCard key={m.id} m={m} onClick={() => !String(m.id).startsWith("optimistic-") && onSelect(m)} />)}
    </div>
  );
}
