/** Generic shimmer placeholder. Compose with utility classes for size:
 *  <Skeleton className="h-4 w-32" /> */
export default function Skeleton({ className = "", rounded = "rounded-sm" }) {
  return <div className={`bg-white/[0.06] animate-pulse ${rounded} ${className}`} aria-hidden="true" />;
}

/** A stack of skeleton rows — the common "list is loading" shape used by
 * Files, Reviews, Conversations, Memory, etc. */
export function SkeletonList({ rows = 5, rowClassName = "h-10" }) {
  return (
    <div className="divide-y divide-white/10" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-4 py-2.5">
          <Skeleton className={rowClassName} />
        </div>
      ))}
    </div>
  );
}

const COLS = { 2: "md:grid-cols-2", 3: "md:grid-cols-3", 4: "md:grid-cols-4", 5: "md:grid-cols-5" };

/** The "stat cards / panel shell" shape used by Dashboard-style grids. */
export function SkeletonGrid({ cols = 3, count = 3, cardClassName = "h-20" }) {
  return (
    <div className={`grid grid-cols-1 ${COLS[cols] || COLS[3]} gap-3`} role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={cardClassName} />
      ))}
    </div>
  );
}
