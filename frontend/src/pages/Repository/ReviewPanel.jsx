import { memo, useEffect, useState } from "react";
import Loader2Icon from "../../assets/icons/loader-2.svg?react";
import PlayIcon from "../../assets/icons/play.svg?react";
import ShieldCheckIcon from "../../assets/icons/shield-check.svg?react";
import Building2Icon from "../../assets/icons/building-2.svg?react";
import ZapIcon from "../../assets/icons/zap.svg?react";
import FlaskConicalIcon from "../../assets/icons/flask-conical.svg?react";
import BookOpenIcon from "../../assets/icons/book-open.svg?react";
import WrenchIcon from "../../assets/icons/wrench.svg?react";
import ChevronDownIcon from "../../assets/icons/chevron-down.svg?react";
import AlertTriangleIcon from "../../assets/icons/alert-triangle.svg?react";
import CheckIcon from "../../assets/icons/check.svg?react";
import BrainCircuitIcon from "../../assets/icons/brain-circuit.svg?react";
import FileCode2Icon from "../../assets/icons/file-code-2.svg?react";
import NetworkIcon from "../../assets/icons/network.svg?react";
import GitForkIcon from "../../assets/icons/git-fork.svg?react";
import MessageSquareTextIcon from "../../assets/icons/message-square-text.svg?react";
import { toast } from "sonner";
import { useWorkspace } from "../../context/WorkspaceContext";
import { useAI } from "../../context/AIContext";
import { isQuotaError, QUOTA_MESSAGE } from "../../context/AIContext";
import { SkeletonList } from "../../components/Skeleton";
import { EmptyState, ErrorState } from "../../components/EmptyState";

const AGENT_META = {
  architect:     { title: "Architect",      icon: Building2Icon,   color: "#2979FF" },
  security:      { title: "Security",       icon: ShieldCheckIcon, color: "#FF3B30" },
  performance:   { title: "Performance",    icon: ZapIcon,         color: "#FFB300" },
  testing:       { title: "Testing",        icon: FlaskConicalIcon, color: "#00E676" },
  documentation: { title: "Documentation", icon: BookOpenIcon,    color: "#D500F9" },
  refactoring:   { title: "Refactoring",   icon: WrenchIcon,      color: "#3FC8E8" },
};

const SEV = {
  critical: { color: "#FF3B30", weight: 5 },
  high:     { color: "#FF9100", weight: 4 },
  medium:   { color: "#FFB300", weight: 3 },
  low:      { color: "#34C759", weight: 2 },
  info:     { color: "#9CA3AF", weight: 1 },
};

const ScoreRing = memo(function ScoreRing({ value }) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.max(0, Math.min(100, value)) / 100) * c;
  const color = value >= 80 ? "#34C759" : value >= 60 ? "#FFB300" : value >= 40 ? "#FF9100" : "#FF3B30";
  return (
    <svg width="96" height="96" viewBox="0 0 96 96" data-testid="review-score-ring">
      <circle cx="48" cy="48" r={r} stroke="rgba(255,255,255,0.1)" strokeWidth="6" fill="none" />
      <circle cx="48" cy="48" r={r} stroke={color} strokeWidth="6" fill="none" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset} transform="rotate(-90 48 48)" style={{ transition: "stroke-dashoffset 0.6s ease" }} />
      <text x="48" y="54" textAnchor="middle" fill="#fff" style={{ fontFamily: "Chivo", fontSize: 22, fontWeight: 600 }}>{value}</text>
    </svg>
  );
})

const SeverityPill = memo(function SeverityPill({ s }) {
  const meta = SEV[s] || SEV.info;
  return <span className="text-[9px] mono uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm border" style={{ color: meta.color, borderColor: `${meta.color}55`, background: `${meta.color}10` }}>{s}</span>;
})

const FindingCard = memo(function FindingCard({ f }) {
  const [open, setOpen] = useState(false);
  const { selectFile, selectedFilePath, fileNodeByPath, askInChat } = useWorkspace();
  const isSelected = f.file_path && f.file_path === selectedFilePath;
  const hasGraphNode = f.file_path && fileNodeByPath.has(f.file_path);

  const toggle = () => {
    setOpen(!open);
    if (f.file_path) selectFile(f.file_path);
  };

  const jump = (e, tab) => {
    e.stopPropagation();
    if (f.file_path) selectFile(f.file_path, { tab });
  };

  return (
    <div className={`border rounded-sm transition-colors ${isSelected ? "border-[#3FC8E8]/50 bg-[#3FC8E8]/5" : "border-white/10 hover:border-white/30"}`} data-testid={`finding-${f.id}`}>
      <button onClick={toggle} className="w-full text-left px-3 py-2.5 flex items-start gap-3">
        <SeverityPill s={f.severity} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-white truncate" style={{ fontFamily: "Chivo" }}>{f.title}</div>
          {f.file_path && <div className="text-[10px] mono text-white/40 truncate mt-0.5">{f.file_path}{f.line ? `:${f.line}` : ""}</div>}
        </div>
        <span className="text-[10px] mono text-white/40 whitespace-nowrap">{Math.round((f.confidence || 0.6) * 100)}%</span>
        <ChevronDownIcon width={14} height={14} className={`text-white/40 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 space-y-2">
          <div className="text-xs text-white/70 leading-relaxed">{f.description}</div>
          {f.recommendation && (
            <div className="text-xs text-white/80 bg-white/[0.03] border-l-2 border-[#3FC8E8] px-2 py-1.5">
              <span className="mono text-[10px] uppercase text-[#3FC8E8] tracking-[0.18em] mr-2">Fix</span>{f.recommendation}
            </div>
          )}
          {f.file_path && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              <button data-testid={`finding-jump-files-${f.id}`} onClick={(e) => jump(e, "files")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30"><FileCode2Icon width={10} height={10} /> Open file</button>
              <button data-testid={`finding-jump-graph-${f.id}`} disabled={!hasGraphNode} onClick={(e) => jump(e, "graph")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30 disabled:opacity-30"><NetworkIcon width={10} height={10} /> Graph</button>
              <button data-testid={`finding-jump-arch-${f.id}`} onClick={(e) => jump(e, "arch")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30"><GitForkIcon width={10} height={10} /> Architecture</button>
              <button data-testid={`finding-ask-${f.id}`}
                onClick={(e) => { e.stopPropagation(); selectFile(f.file_path); askInChat(`Explain this finding in ${f.file_path}${f.line ? `:${f.line}` : ""}: "${f.title}" — ${f.description || ""}`); }}
                className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30">
                <MessageSquareTextIcon width={10} height={10} /> Ask
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
})

const AgentCard = memo(function AgentCard({ report }) {
  const meta = AGENT_META[report.agent] || { title: report.agent, icon: WrenchIcon, color: "#fff" };
  const Icon = meta.icon;
  const counts = (report.findings || []).reduce((acc, f) => ({ ...acc, [f.severity]: (acc[f.severity] || 0) + 1 }), {});
  return (
    <div className="glass-panel border border-white/10 rounded-xl" data-testid={`agent-card-${report.agent}`}>
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-3">
        <div className="w-8 h-8 rounded-sm flex items-center justify-center" style={{ background: `${meta.color}20`, color: meta.color }}>
          <Icon width={15} height={15} />
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium" style={{ fontFamily: "Chivo" }}>{meta.title}</div>
          <div className="text-[10px] mono text-white/40 uppercase tracking-[0.18em]">{report.status} {report.status === "done" && `· ${report.duration_ms}ms`}</div>
        </div>
        {report.status === "running" && <Loader2Icon width={14} height={14} className="animate-spin text-[#3FC8E8]" />}
        {report.status === "done" && <span className="text-xl font-semibold" style={{ color: meta.color, fontFamily: "Chivo" }}>{report.score}</span>}
        {report.status === "failed" && <AlertTriangleIcon width={14} height={14} className="text-[#FF3B30]" />}
      </div>
      <div className="p-3 space-y-2">
        {report.summary && <div className="text-xs text-white/70 leading-relaxed">{report.summary}</div>}
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(counts).sort((a, b) => (SEV[b[0]]?.weight || 0) - (SEV[a[0]]?.weight || 0)).map(([sev, n]) => (
            <span key={sev} className="text-[10px] mono uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm border" style={{ color: SEV[sev].color, borderColor: `${SEV[sev].color}55` }}>{n} {sev}</span>
          ))}
          {(report.findings || []).length === 0 && report.status === "done" && (
            <span className="text-[10px] mono text-white/40 flex items-center gap-1"><CheckIcon width={10} height={10} /> no findings</span>
          )}
        </div>
        {(report.findings || []).length > 0 && (
          <div className="space-y-1.5 pt-1">
            {report.findings.slice(0, 8).map((f) => <FindingCard key={f.id} f={f} />)}
          </div>
        )}
        {report.error && (
          <div className="text-xs text-[#FF3B30] mono">
            {(report.error.includes("RESOURCE_EXHAUSTED") || report.error.toLowerCase().includes("quota"))
              ? QUOTA_MESSAGE
              : report.error}
          </div>
        )}
      </div>
    </div>
  );
})

export default function ReviewPanel({ repoId, repoReady }) {
  const {
    getReview, loadReviewsInitial, setCurrentReview, pollReview, stopReviewPoll,
    startReview, importReviewToMemory, setReviewImported,
  } = useAI();
  const { reviews, current, loading, error, running, importing, imported } = getReview(repoId);

  useEffect(() => { loadReviewsInitial(repoId); }, [repoId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!current || ["done", "failed"].includes(current.status) || String(current.id).startsWith("optimistic-")) {
      stopReviewPoll(repoId);
      return;
    }
    pollReview(repoId, current.id);
    return () => stopReviewPoll(repoId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId, current?.id, current?.status]);

  const handleStartReview = async () => {
    try {
      await startReview(repoId);
      toast.success("Multi-agent review started");
    } catch (err) {
      const msg = isQuotaError(err) ? QUOTA_MESSAGE : (err?.response?.data?.detail || "Failed to start review");
      toast.error(msg);
    }
  };

  const importToMemory = async () => {
    if (!current) return;
    setReviewImported(repoId, true);
    try {
      const r = await importReviewToMemory(repoId, current.id);
      toast.success(`Saved ${r.added} finding${r.added === 1 ? "" : "s"} to Engineering Memory`);
    } catch (err) {
      setReviewImported(repoId, false);
      toast.error(err?.response?.data?.detail || "Failed to save findings to memory");
    }
  };

  const retry = () => loadReviewsInitial(repoId);

  if (error) return <ErrorState message={error} onRetry={retry} testId="review-error" />;

  if (loading) {
    return (
      <div className="space-y-3" data-testid="review-panel-loading">
        <div className="h-6 w-56 bg-white/[0.06] rounded-sm animate-pulse" />
        <SkeletonList rows={3} rowClassName="h-16" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="review-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] mono text-white/40">{"// multi-agent code review"}</div>
          <h2 className="text-xl tracking-tight font-medium mt-0.5" style={{ fontFamily: "Chivo" }}>AI Code Review</h2>
          <div className="text-xs text-white/50 mt-1">Six specialist perspectives on architecture, security, performance, testing, documentation, and maintainability.</div>
        </div>
        <div className="flex items-center gap-2">
          {reviews.length > 1 && (
            <select data-testid="review-history-select" value={current?.id || ""} onChange={(e) => setCurrentReview(repoId, reviews.find((r) => r.id === e.target.value))}
              className="glass-panel-soft border border-white/10 rounded-xl text-xs mono px-2 py-1.5 text-white">
              {reviews.map((r) => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString()} · {r.status}</option>)}
            </select>
          )}
          <button data-testid="run-review-button" onClick={handleStartReview} disabled={!repoReady || running || (current && current.status === "running")} aria-label="Run multi-agent code review"
            className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2">
            {running ? <Loader2Icon width={14} height={14} className="animate-spin" aria-hidden="true" /> : <PlayIcon width={13} height={13} aria-hidden="true" />} Run review
          </button>
        </div>
      </div>

      {!current && (
        <EmptyState testId="review-empty" title="No reviews yet."
          subtitle="Run all six specialists: architecture, security, performance, testing, docs and refactoring. A review can take several minutes on the free tier."
          action={repoReady ? { label: "Run review", onClick: handleStartReview } : undefined} />
      )}

      {current && (
        <div className="space-y-4 animate-in fade-in duration-200" key={current.id}>
          <div className="glass-panel border border-white/10 rounded-xl p-5 flex flex-col md:flex-row gap-5 items-start" data-testid="review-overview">
            <ScoreRing value={current.overall_score || 0} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-[10px] mono uppercase tracking-[0.18em] px-2 py-0.5 rounded-sm border border-white/10 text-white/60" data-testid="review-status">{current.status}</span>
                <span className="text-[10px] mono text-white/40">{new Date(current.created_at).toLocaleString()}</span>
                {current.status === "done" && (
                  <button data-testid="review-import-memory" onClick={importToMemory} disabled={importing || imported} aria-label="Save review findings to Engineering Memory"
                    className="ml-auto text-[11px] mono text-[#3FC8E8] hover:text-white border border-[#3FC8E8]/40 hover:bg-[#3FC8E8]/10 disabled:opacity-70 px-2 py-1 rounded-sm flex items-center gap-1.5 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]">
                    {importing ? <Loader2Icon width={11} height={11} className="animate-spin" aria-hidden="true" /> : imported ? <CheckIcon width={11} height={11} aria-hidden="true" /> : <BrainCircuitIcon width={11} height={11} aria-hidden="true" />}
                    {imported ? "Saved to Memory" : "Save findings to Memory"}
                  </button>
                )}
              </div>
              <h3 className="text-lg tracking-tight font-medium mt-2" style={{ fontFamily: "Chivo" }}>Executive Summary</h3>
              <p className="text-sm text-white/75 leading-relaxed mt-1" data-testid="review-summary">
                {current.summary || (current.status === "running" ? "Specialists are reviewing the repository…" : "Awaiting summary…")}
              </p>
              {current.status !== "done" && (
                <div className="mt-3 h-1 bg-white/5 rounded-sm overflow-hidden">
                  <div className="h-full bg-[#3FC8E8] transition-all duration-300" style={{ width: `${current.progress || 0}%` }} />
                </div>
              )}
            </div>
          </div>

          {(current.action_plan || []).length > 0 && (
            <div className="glass-panel border border-white/10 rounded-xl p-5" data-testid="review-action-plan">
              <h3 className="text-sm font-medium tracking-tight mb-3" style={{ fontFamily: "Chivo" }}>Prioritized Action Plan</h3>
              <ol className="space-y-2">
                {current.action_plan.map((a, i) => (
                  <li key={i} className="flex gap-3 text-sm text-white/80">
                    <span className="text-[10px] mono text-[#3FC8E8] w-5 shrink-0 pt-0.5">[{i + 1}]</span>
                    <span className="leading-relaxed">{a}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {current.agents.length === 0 && current.status === "running" ? (
            <SkeletonList rows={2} rowClassName="h-24" />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {current.agents.map((a) => <AgentCard key={a.agent} report={a} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
