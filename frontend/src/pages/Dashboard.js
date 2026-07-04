import { Link } from "react-router-dom";
import { ArrowUpRight, GitBranch, FileCode2, Network, MessageSquare, Activity } from "lucide-react";
import { useFetch } from "../hooks/useFetch";
import { SkeletonGrid } from "../components/ui/skeleton";
import { ErrorState } from "../components/ui/state";

const StatCard = ({ label, value, hint, testId, icon: Icon }) => (
  <div data-testid={testId} className="glass-panel border border-white/10 rounded-xl p-4 hover:border-white/30 transition-colors duration-150">
    <div className="flex items-center justify-between">
      <div className="text-[10px] uppercase tracking-[0.18em] mono text-white/40">{label}</div>
      <Icon size={14} className="text-white/40" aria-hidden="true" />
    </div>
    <div className="text-3xl font-semibold mt-3 tracking-tighter" style={{ fontFamily: "Chivo" }}>{value}</div>
    {hint && <div className="text-[11px] mt-1 text-white/40">{hint}</div>}
  </div>
);

export default function Dashboard() {
  const { data: stats, loading, error, retry } = useFetch("/stats");

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="dashboard-root">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// overview"}</div>
          <h1 className="text-3xl font-semibold tracking-tighter mt-1" style={{ fontFamily: "Chivo" }}>Engineering Dashboard</h1>
        </div>
        <Link to="/repositories" data-testid="dashboard-add-repo" className="text-sm bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black px-4 py-2 rounded-lg flex items-center gap-2 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2">
          + Add repository <ArrowUpRight size={14} aria-hidden="true" />
        </Link>
      </div>

      {error && <ErrorState message={error} onRetry={retry} testId="dashboard-error" />}

      {!error && loading && (
        <>
          <SkeletonGrid cols={5} count={6} cardClassName="h-[92px]" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 h-48 bg-white/[0.06] rounded-sm animate-pulse" />
            <div className="h-48 bg-white/[0.06] rounded-sm animate-pulse" />
          </div>
        </>
      )}

      {!error && !loading && (
        <div className="animate-in fade-in duration-200">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard testId="stat-repos" label="Repos" value={stats?.repos_count ?? 0} icon={GitBranch} />
            <StatCard testId="stat-files" label="Files" value={stats?.files_indexed ?? 0} icon={FileCode2} />
            <StatCard testId="stat-nodes" label="Graph nodes" value={stats?.nodes ?? 0} icon={Network} />
            <StatCard testId="stat-edges" label="Graph edges" value={stats?.edges ?? 0} icon={Network} />
            <StatCard testId="stat-chunks" label="Chunks" value={stats?.chunks ?? 0} icon={FileCode2} />
            <StatCard testId="stat-llm" label="LLM calls" value={stats?.llm_calls ?? 0} icon={MessageSquare} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
            <div className="lg:col-span-2 glass-panel border border-white/10 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] mono text-white/40">{"// ingestion pipeline"}</div>
                  <h2 className="text-lg tracking-tight font-medium mt-1" style={{ fontFamily: "Chivo" }}>How CodeOS understands your code</h2>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                {[
                  { n: "1", t: "Clone / Upload", d: "GitHub or ZIP" },
                  { n: "2", t: "Tree-sitter parse", d: "AST + symbols" },
                  { n: "3", t: "Knowledge Graph", d: "Nodes + edges" },
                  { n: "4", t: "Hybrid retrieval", d: "Vector + graph" },
                ].map((s) => (
                  <div key={s.n} className="border border-white/10 p-3 rounded-xl glass-panel-soft">
                    <div className="text-[10px] mono text-[#3FC8E8]">[{s.n}]</div>
                    <div className="text-white text-xs mt-1 font-medium">{s.t}</div>
                    <div className="text-white/40 text-[11px] mt-0.5">{s.d}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-panel border border-white/10 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Activity size={14} className="text-[#3FC8E8]" aria-hidden="true" />
                <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Recent activity</h2>
              </div>
              <div className="space-y-2 max-h-72 overflow-auto pr-1">
                {(stats?.recent_activity || []).length === 0 && (
                  <div className="text-white/40 text-xs">No activity yet. Add a repository to get started.</div>
                )}
                {(stats?.recent_activity || []).map((a) => (
                  <div key={a.id} className="border-l-2 border-white/10 pl-3 py-1 hover:border-[#3FC8E8] transition-colors duration-150">
                    <div className="text-xs text-white/80">{a.message}</div>
                    <div className="text-[10px] mono text-white/30">{new Date(a.created_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
