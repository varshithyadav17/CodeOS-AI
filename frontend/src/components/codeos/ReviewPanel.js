import { memo, useEffect, useState, useRef } from "react";
import { api } from "../../lib/api";
import { Loader2, Play, ShieldCheck, Building2, Zap, FlaskConical, BookOpen, Wrench, ChevronDown, AlertTriangle, Check, BrainCircuit, FileCode2, Network, GitFork, MessageSquareText } from "lucide-react";
import { toast } from "sonner";
import { useWorkspace } from "../../context/WorkspaceContext";
import { SkeletonList } from "../ui/skeleton";
import { EmptyState, ErrorState } from "../ui/state";

const AGENT_META = {
  architect: { title: "Architect", icon: Building2, color: "#2979FF" },
  security: { title: "Security", icon: ShieldCheck, color: "#FF3B30" },
  performance: { title: "Performance", icon: Zap, color: "#FFB300" },
  testing: { title: "Testing", icon: FlaskConical, color: "#00E676" },
  documentation: { title: "Documentation", icon: BookOpen, color: "#D500F9" },
  refactoring: { title: "Refactoring", icon: Wrench, color: "#3FC8E8" },
};

const SEV = {
  critical: { color: "#FF3B30", weight: 5 },
  high: { color: "#FF9100", weight: 4 },
  medium: { color: "#FFB300", weight: 3 },
  low: { color: "#34C759", weight: 2 },
  info: { color: "#9CA3AF", weight: 1 },
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
    // Selecting/expanding a finding updates the shared workspace selection
    // so Files/Graph/Architecture/Timeline all reflect the file it's about.
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
        <ChevronDown size={14} className={`text-white/40 transition-transform ${open ? "rotate-180" : ""}`} />
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
              <button data-testid={`finding-jump-files-${f.id}`} onClick={(e) => jump(e, "files")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30"><FileCode2 size={10} /> Open file</button>
              <button data-testid={`finding-jump-graph-${f.id}`} disabled={!hasGraphNode} onClick={(e) => jump(e, "graph")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30 disabled:opacity-30"><Network size={10} /> Graph</button>
              <button data-testid={`finding-jump-arch-${f.id}`} onClick={(e) => jump(e, "arch")} className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30"><GitFork size={10} /> Architecture</button>
              <button
                data-testid={`finding-ask-${f.id}`}
                onClick={(e) => { e.stopPropagation(); selectFile(f.file_path); askInChat(`Explain this finding in ${f.file_path}${f.line ? `:${f.line}` : ""}: "${f.title}" — ${f.description || ""}`); }}
                className="text-[10px] mono flex items-center gap-1 px-2 py-1 rounded-sm border border-white/10 text-white/60 hover:text-white hover:border-white/30"
              >
                <MessageSquareText size={10} /> Ask
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
})

const AgentCard = memo(function AgentCard({ report }) {
  const meta = AGENT_META[report.agent] || { title: report.agent, icon: Wrench, color: "#fff" };
  const Icon = meta.icon;
  const counts = (report.findings || []).reduce((acc, f) => ({ ...acc, [f.severity]: (acc[f.severity] || 0) + 1 }), {});
  return (
    <div className="glass-panel border border-white/10 rounded-xl" data-testid={`agent-card-${report.agent}`}>
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-3">
        <div className="w-8 h-8 rounded-sm flex items-center justify-center" style={{ background: `${meta.color}20`, color: meta.color }}>
          <Icon size={15} />
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium" style={{ fontFamily: "Chivo" }}>{meta.title}</div>
          <div className="text-[10px] mono text-white/40 uppercase tracking-[0.18em]">{report.status} {report.status === "done" && `· ${report.duration_ms}ms`}</div>
        </div>
        {report.status === "running" && <Loader2 size={14} className="animate-spin text-[#3FC8E8]" />}
        {report.status === "done" && <span className="text-xl font-semibold" style={{ color: meta.color, fontFamily: "Chivo" }}>{report.score}</span>}
        {report.status === "failed" && <AlertTriangle size={14} className="text-[#FF3B30]" />}
      </div>
      <div className="p-3 space-y-2">
        {report.summary && <div className="text-xs text-white/70 leading-relaxed">{report.summary}</div>}
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(counts).sort((a, b) => (SEV[b[0]]?.weight || 0) - (SEV[a[0]]?.weight || 0)).map(([sev, n]) => (
            <span key={sev} className="text-[10px] mono uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm border" style={{ color: SEV[sev].color, borderColor: `${SEV[sev].color}55` }}>{n} {sev}</span>
          ))}
          {(report.findings || []).length === 0 && report.status === "done" && (
            <span className="text-[10px] mono text-white/40 flex items-center gap-1"><Check size={10} /> no findings</span>
          )}
        </div>
        {(report.findings || []).length > 0 && (
          <div className="space-y-1.5 pt-1">
            {report.findings.slice(0, 8).map((f) => <FindingCard key={f.id} f={f} />)}
          </div>
        )}
        {report.error && <div className="text-xs text-[#FF3B30] mono">{report.error}</div>}
      </div>
    </div>
  );
})

export default function ReviewPanel({ repoId, repoReady }) {
  const [reviews, setReviews] = useState([]);
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(false);
  const pollRef = useRef(null);

  const loadList = async () => {
    const r = await api.get(`/repos/${repoId}/reviews`);
    setReviews(r.data);
    setError(null);
    setCurrent((cur) => {
      if (!cur) return r.data.length > 0 ? r.data[0] : null;
      // Don't clobber an optimistic placeholder (negative/temp id) with a
      // list response that hasn't picked it up yet.
      if (String(cur.id).startsWith("optimistic-")) return cur;
      return r.data.find((x) => x.id === cur.id) || cur;
    });
    return r.data;
  };

  const loadInitial = () => {
    setLoading(true);
    loadList().catch((e) => setError(e?.response?.data?.detail || "Failed to load reviews.")).finally(() => setLoading(false));
  };

  useEffect(() => { setImported(false); }, [current?.id]);

  useEffect(loadInitial, [repoId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!current || ["done", "failed"].includes(current.status) || String(current.id).startsWith("optimistic-")) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const r = await api.get(`/reviews/${current.id}`);
        setCurrent(r.data);
        if (["done", "failed"].includes(r.data.status)) loadList().catch(() => {});
      } catch {
        // Transient network hiccups during polling shouldn't interrupt the
        // view — the next tick will retry automatically.
      }
    }, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, current?.status]);

  // Optimistic start: a placeholder "running" review appears in the
  // dropdown and as the active card immediately, before the POST resolves.
  // If the request fails, the placeholder is removed and the previous
  // selection is restored.
  const startReview = async () => {
    setRunning(true);
    const placeholder = {
      id: `optimistic-${Date.now()}`,
      status: "running",
      progress: 0,
      created_at: new Date().toISOString(),
      summary: "",
      agents: [],
      action_plan: [],
      overall_score: 0,
    };
    const prevCurrent = current;
    setReviews((rs) => [placeholder, ...rs]);
    setCurrent(placeholder);
    try {
      const r = await api.post(`/repos/${repoId}/reviews`);
      toast.success("Multi-agent review started");
      setReviews((rs) => rs.map((x) => (x.id === placeholder.id ? r.data : x)));
      setCurrent(r.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to start review");
      setReviews((rs) => rs.filter((x) => x.id !== placeholder.id));
      setCurrent(prevCurrent);
    } finally { setRunning(false); }
  };

  // Optimistic import: button flips to a confirmed state immediately;
  // reverts to normal on failure with an error toast.
  const importToMemory = async () => {
    if (!current) return;
    setImporting(true);
    setImported(true);
    try {
      const r = await api.post(`/memory/import/${current.id}`);
      toast.success(`Saved ${r.data.added} finding${r.data.added === 1 ? "" : "s"} to Engineering Memory`);
    } catch (err) {
      setImported(false); // rollback
      toast.error(err?.response?.data?.detail || "Failed to save findings to memory");
    } finally {
      setImporting(false);
    }
  };

  if (error) return <ErrorState message={error} onRetry={loadInitial} testId="review-error" />;

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
          <div className="text-xs text-white/50 mt-1">Six specialist agents review your repo in parallel. Powered by Gemini 2.5 Pro.</div>
        </div>
        <div className="flex items-center gap-2">
          {reviews.length > 1 && (
            <select
              data-testid="review-history-select"
              value={current?.id || ""}
              onChange={(e) => setCurrent(reviews.find((r) => r.id === e.target.value))}
              className="glass-panel-soft border border-white/10 rounded-xl text-xs mono px-2 py-1.5 text-white"
            >
              {reviews.map((r) => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString()} · {r.status}</option>)}
            </select>
          )}
          <button
            data-testid="run-review-button"
            onClick={startReview}
            disabled={!repoReady || running || (current && current.status === "running")}
            aria-label="Run multi-agent code review"
            className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2"
          >
            {running ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Play size={13} aria-hidden="true" />} Run review
          </button>
        </div>
      </div>

      {!current && (
        <EmptyState
          testId="review-empty"
          title="No reviews yet."
          subtitle="Run a review to launch all six specialist agents (architecture, security, performance, testing, docs, refactoring) in parallel."
          action={repoReady ? { label: "Run review", onClick: startReview } : undefined}
        />
      )}

      {current && (
        <div className="space-y-4 animate-in fade-in duration-200" key={current.id}>
          {/* Header card with overall score */}
          <div className="glass-panel border border-white/10 rounded-xl p-5 flex flex-col md:flex-row gap-5 items-start" data-testid="review-overview">
            <ScoreRing value={current.overall_score || 0} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-[10px] mono uppercase tracking-[0.18em] px-2 py-0.5 rounded-sm border border-white/10 text-white/60" data-testid="review-status">{current.status}</span>
                <span className="text-[10px] mono text-white/40">{new Date(current.created_at).toLocaleString()}</span>
                {current.status === "done" && (
                  <button
                    data-testid="review-import-memory"
                    onClick={importToMemory}
                    disabled={importing || imported}
                    aria-label="Save review findings to Engineering Memory"
                    className="ml-auto text-[11px] mono text-[#3FC8E8] hover:text-white border border-[#3FC8E8]/40 hover:bg-[#3FC8E8]/10 disabled:opacity-70 px-2 py-1 rounded-sm flex items-center gap-1.5 transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
                  >
                    {importing ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : imported ? <Check size={11} aria-hidden="true" /> : <BrainCircuit size={11} aria-hidden="true" />}
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

          {/* Action plan */}
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

          {/* Agent grid */}
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
