import Skeleton, { SkeletonGrid } from "../../components/Skeleton";

/** Skeleton shown while the repository detail is first loading. */
export default function LoadingOverlay() {
  return (
    <div className="p-6 md:p-8 space-y-5" data-testid="repo-detail-loading">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-8 w-72" />
      <SkeletonGrid cols={5} count={5} cardClassName="h-16" />
      <Skeleton className="h-9 w-full max-w-xl" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
