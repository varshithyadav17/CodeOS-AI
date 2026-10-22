import { SkeletonList } from "../../components/Skeleton";
import { EmptyState, ErrorState } from "../../components/EmptyState";
import RepositoryCard from "./RepositoryCard";

/** The "Your repositories" panel: header count, loading/error/empty
 * states, and the list of RepositoryCards. */
export default function RepositoryList({ repos, loading, error, onRetry, onReingest, onDelete }) {
  return (
    <div className="glass-panel border border-white/10 rounded-xl" data-testid="repos-list">
      <div className="px-5 py-3 border-b border-white/10 flex items-center justify-between">
        <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Your repositories</h2>
        <span className="text-[10px] mono text-white/40 uppercase tracking-[0.18em]">{repos.length} total</span>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={onRetry} testId="repos-error" />
      ) : loading ? (
        <SkeletonList rows={4} rowClassName="h-14" />
      ) : repos.length === 0 ? (
        <EmptyState title="No repositories yet." subtitle="Add one above via GitHub URL or ZIP upload to get started." testId="repos-empty" />
      ) : (
        <ul className="divide-y divide-white/10">
          {repos.map((r) => (
            <RepositoryCard key={r.id} r={r} onReingest={onReingest} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </div>
  );
}
