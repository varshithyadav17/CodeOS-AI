import { useEffect, useMemo, useState, useCallback } from "react";
import ReactFlow, { Background, Controls, MiniMap, useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";
import { api } from "../../lib/api";
import KGNodeView from "./KGNodeView";
import { dependencyPositions, graphEdges, NODE_COLORS } from "../../lib/graphLayout";
import Loader2Icon from "../../assets/icons/loader-2.svg?react";
import AlertTriangleIcon from "../../assets/icons/alert-triangle.svg?react";
import SearchIcon from "../../assets/icons/search.svg?react";
import GitForkIcon from "../../assets/icons/git-fork.svg?react";
import LayersIcon from "../../assets/icons/layers.svg?react";
import PackageIcon from "../../assets/icons/package.svg?react";
import NetworkIcon from "../../assets/icons/network.svg?react";
import SkullIcon from "../../assets/icons/skull.svg?react";
import ZapIcon from "../../assets/icons/zap.svg?react";
import XIcon from "../../assets/icons/x.svg?react";
import MessageSquareTextIcon from "../../assets/icons/message-square-text.svg?react";
import RefreshCwIcon from "../../assets/icons/refresh-cw.svg?react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { ErrorState } from "../../components/EmptyState";

const nodeTypes = { kg: KGNodeView };
const VIEWS = [
  { k: "call",       label: "Call Graph",  icon: GitForkIcon },
  { k: "dependency", label: "Dependency",  icon: NetworkIcon },
  { k: "package",    label: "Package",     icon: PackageIcon },
  { k: "service",    label: "Service",     icon: LayersIcon },
];

export default function ArchitecturePanel({ repoId, repoReady }) {
  const { repo, selectedNodeId, selectNode, clearSelection, nodeById, askInChat, setActiveTab } = useWorkspace();
  const [view, setView] = useState("call");
  const [data, setData] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [graphError, setGraphError] = useState(null);
  const [search, setSearch] = useState("");
  const [flowInstance, setFlowInstance] = useState(null);
  const [cycles, setCycles] = useState(null);
  const [cyclesError, setCyclesError] = useState(null);
  const [deadCode, setDeadCode] = useState(null);
  const [deadError, setDeadError] = useState(null);
  const [impact, setImpact] = useState(null);
  const [flow, setFlow] = useState(null);
  const [side, setSide] = useState(() => (selectedNodeId ? "impact" : "cycles"));

  const load = useCallback(async (v, signal) => {
    setLoading(true);
    setGraphError(null);
    try {
      const r = await api.get(`/repos/${repoId}/architecture/graph`, { params: { view: v, limit: 200 }, signal });
      setData(r.data);
    } catch (e) {
      if (signal?.aborted || e.code === "ERR_CANCELED") return;
      setGraphError(e?.response?.data?.detail || "Failed to load architecture graph.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    if (!repoReady) return;
    const controller = new AbortController();
    load(view, controller.signal);
    return () => controller.abort();
  }, [view, repoReady, load]);

  const loadSidePanels = useCallback((signal) => {
    setCyclesError(null);
    api.get(`/repos/${repoId}/architecture/cycles`, { signal })
      .then((r) => setCycles(r.data))
      .catch((e) => { if (!signal?.aborted && e.code !== "ERR_CANCELED") setCyclesError(e?.response?.data?.detail || "Failed to analyze cycles."); });
    setDeadError(null);
    api.get(`/repos/${repoId}/architecture/dead-code`, { signal })
      .then((r) => setDeadCode(r.data))
      .catch((e) => { if (!signal?.aborted && e.code !== "ERR_CANCELED") setDeadError(e?.response?.data?.detail || "Failed to analyze dead code."); });
  }, [repoId]);

  useEffect(() => {
    if (!repoReady) return;
    const controller = new AbortController();
    loadSidePanels(controller.signal);
    return () => controller.abort();
  }, [repoReady, loadSidePanels]);

  const [impactNonce, setImpactNonce] = useState(0);
  useEffect(() => {
    if (!repoReady || !selectedNodeId) { setImpact(null); return; }
    const controller = new AbortController();
    setImpact(null);
    api.get(`/repos/${repoId}/architecture/impact/${selectedNodeId}`, { params: { depth: 3 }, signal: controller.signal })
      .then((r) => setImpact(r.data))
      .catch((e) => {
        if (controller.signal.aborted || e.code === "ERR_CANCELED") return;
        setImpact({ error: true, message: e?.response?.data?.detail || "Failed to load impact analysis." });
      });
    return () => controller.abort();
  }, [selectedNodeId, repoReady, repoId, impactNonce]);

  const annotated = useMemo(() => {
    const inCycle = new Set();
    (cycles?.cycles || []).forEach((c) => c.nodes.forEach((n) => inCycle.add(n.id)));
    return {
      nodes: data.nodes,
      edges: data.edges.map((e) => ({ ...e, metadata: { ...(e.metadata || {}), in_cycle: inCycle.has(e.source_id) && inCycle.has(e.target_id) } })),
    };
  }, [data, cycles]);

  const filtered = useMemo(() => {
    if (!search.trim()) return annotated;
    const q = search.toLowerCase();
    const keep = annotated.nodes.filter((n) => (n.name || "").toLowerCase().includes(q) || (n.file_path || "").toLowerCase().includes(q));
    const ids = new Set(keep.map((n) => n.id));
    return { nodes: keep, edges: annotated.edges.filter((e) => ids.has(e.source_id) && ids.has(e.target_id)) };
  }, [annotated, search]);

  const positions = useMemo(() => dependencyPositions(filtered.nodes, filtered.edges), [filtered.nodes, filtered.edges]);
  const positionKey = JSON.stringify(positions);
  useEffect(() => {
    const timer = setTimeout(() => flowInstance?.fitView({ padding: 0.2, maxZoom: 1 }), 80);
    return () => clearTimeout(timer);
  }, [flowInstance, positionKey]);
  const flowNodes = useMemo(
    () => filtered.nodes.map((n) => ({
      id: n.id, type: "kg", position: positions[n.id] || { x: 0, y: 0 },
      data: { id: n.id, type: n.type, label: n.name, file: n.file_path, highlight: n.metadata?.is_root || n.id === selectedNodeId },
    })),
    [filtered.nodes, positions, selectedNodeId]
  );
  const flowEdges = useMemo(() => graphEdges(filtered.edges, selectedNodeId), [filtered.edges, selectedNodeId]);
  const [n, setN, onNodesChange] = useNodesState(flowNodes);
  const [e, setE, onEdgesChange] = useEdgesState(flowEdges);
  useEffect(() => { setN(flowNodes); setE(flowEdges); }, [flowNodes, flowEdges, setN, setE]);

  const selectedInfo = useMemo(() => {
    if (!selectedNodeId) return null;
    const fromView = filtered.nodes.find((x) => x.id === selectedNodeId);
    const fromKg = nodeById.get(selectedNodeId);
    const src = fromView || fromKg;
    if (!src) return { id: selectedNodeId, label: selectedNodeId, file: null, type: null };
    return { id: src.id, label: src.name || src.qualified_name, file: src.file_path, type: src.type, qualified_name: src.qualified_name };
  }, [selectedNodeId, filtered.nodes, nodeById]);

  const onNodeClick = (_, node) => {
    selectNode(node.id);
    setSide("impact");
    setFlow(null);
  };

  const traceFlow = async () => {
    if (!selectedNodeId) return;
    setSide("flow"); setFlow(null);
    try {
      const r = await api.get(`/repos/${repoId}/architecture/flow/${selectedNodeId}`, { params: { depth: 3 } });
      setFlow(r.data);
      setData(r.data);
    } catch (e) {
      setFlow({ error: true, message: e?.response?.data?.detail || "Failed to trace execution flow." });
    }
  };

  const SIDE_TABS = [
    { k: "cycles", label: "Cycles", icon: AlertTriangleIcon },
    { k: "dead",   label: "Dead",   icon: SkullIcon },
    { k: "impact", label: "Impact", icon: ZapIcon },
    ...(flow ? [{ k: "flow", label: "Flow", icon: GitForkIcon }] : []),
  ];

  return (
    <div className="space-y-3" data-testid="arch-panel">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex border border-white/10 rounded-sm overflow-hidden" data-testid="arch-view-toggle">
          {VIEWS.map((v) => {
            const Icon = v.icon;
            return (
              <button
                key={v.k}
                data-testid={`arch-view-${v.k}`}
                aria-pressed={view === v.k}
                onClick={() => setView(v.k)}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 transition-colors ${view === v.k ? "bg-[#3FC8E8] text-black" : "glass-panel text-white/60 hover:text-white"}`}
              >
                <Icon width={12} height={12} /> {v.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-1.5 glass-panel-soft border border-white/10 rounded-xl px-2 py-1.5 flex-1 max-w-xs">
          <SearchIcon width={12} height={12} className="text-white/40" />
          <input
            data-testid="arch-search"
            aria-label="Filter architecture symbols"
            value={search}
            onChange={(ev) => setSearch(ev.target.value)}
            placeholder="Filter nodes…"
            className="bg-transparent text-xs mono outline-none flex-1 text-white placeholder:text-white/30"
          />
        </div>
        <div className="text-[10px] mono text-white/40 ml-auto">{filtered.nodes.length} nodes · {filtered.edges.length} edges</div>
      </div>

      <div className="grid grid-cols-12 gap-3">
        {/* Graph */}
        <div className="col-span-12 lg:col-span-8 glass-panel-soft border border-white/10 rounded-xl dot-grid h-[560px] relative" data-testid="arch-graph">
          {loading && !graphError && (
            <div className="absolute inset-0 flex items-center justify-center text-white/40 z-10 bg-black/50" role="status">
              <Loader2Icon width={16} height={16} className="animate-spin mr-2" aria-hidden="true" /> Loading…
            </div>
          )}
          {graphError && (
            <div className="absolute inset-0 flex items-center justify-center z-10 bg-black/70 p-6">
              <ErrorState message={graphError} onRetry={() => load(view)} testId="arch-graph-error" compact />
            </div>
          )}
          {!loading && !graphError && filtered.nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center z-10 p-6 text-center">
              <div>
                <div className="text-white/50 text-sm">No nodes match{search.trim() ? ` "${search}"` : " this view"}.</div>
                {search.trim() && <button onClick={() => setSearch("")} className="text-xs mono text-[#3FC8E8] hover:text-white mt-2">Clear filter</button>}
              </div>
            </div>
          )}
          <ReactFlow onInit={setFlowInstance} nodesConnectable={false} nodes={n} edges={e} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} fitView minZoom={0.03} proOptions={{ hideAttribution: true }}>
            <Background color="rgba(255,255,255,0.05)" gap={20} />
            <Controls className="rf-controls-glass" showInteractive={false} />
            <MiniMap nodeColor={(node) => NODE_COLORS[node.data.type] || "#5cdbc7"} maskColor="rgba(0,0,0,0.7)" style={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)" }} />
          </ReactFlow>
          <div className="absolute bottom-3 left-16 right-36 pointer-events-none glass-panel border border-white/10 rounded-xl p-2 text-[10px] mono flex flex-wrap gap-3" data-testid="arch-legend">
            {[
              { l: "file", c: NODE_COLORS.file }, { l: "class", c: NODE_COLORS.class },
              { l: "function/method", c: NODE_COLORS.function }, { l: "package", c: "#3FC8E8" },
            ].map((x) => (
              <span key={x.l} className="flex items-center gap-1 text-white/60"><span className="w-2 h-2 rounded-full" style={{ background: x.c }} />{x.l}</span>
            ))}
            <span className="flex items-center gap-1 text-[#FF3B30]"><span className="w-2 h-2 rounded-full bg-[#FF3B30]" />cycle</span>
          </div>
        </div>

        {/* Right side intelligence panel */}
        <div className="col-span-12 lg:col-span-4 glass-panel border border-white/10 rounded-xl flex flex-col h-[560px]" data-testid="arch-side">
          <div className="flex border-b border-white/10 text-[10px] mono uppercase tracking-[0.16em]">
            {SIDE_TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button key={t.k} data-testid={`arch-side-${t.k}`} onClick={() => setSide(t.k)}
                  className={`flex-1 px-2 py-2 flex items-center justify-center gap-1.5 ${side === t.k ? "bg-white/10 text-white" : "text-white/50 hover:text-white"}`}>
                  <Icon width={11} height={11} /> {t.label}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-auto p-3 text-xs">
            {side === "cycles" && (
              <div data-testid="arch-cycles">
                {cyclesError ? <ErrorState message={cyclesError} onRetry={() => loadSidePanels()} testId="arch-cycles-error" compact /> :
                !cycles ? <div className="text-white/40 flex items-center gap-1.5" role="status"><Loader2Icon width={12} height={12} className="animate-spin" aria-hidden="true" />Analyzing…</div> :
                cycles.count === 0 ? <div className="text-[#34C759]">No circular dependencies detected 🎉</div> :
                <>
                  <div className="text-white/80 mb-2">{cycles.count} cycle{cycles.count > 1 ? "s" : ""} detected.</div>
                  {cycles.cycles.slice(0, 10).map((c, i) => (
                    <div key={i} className="border border-[#FF3B30]/30 bg-[#FF3B30]/5 rounded-sm p-2 mb-2" data-testid={`cycle-${i}`}>
                      <div className="text-[10px] mono text-[#FF3B30] uppercase tracking-[0.16em] mb-1">Cycle · {c.size} files</div>
                      {c.nodes.map((cn) => (
                        <button key={cn.id} data-testid={`cycle-file-${cn.id}`} onClick={() => { selectNode(cn.id); setSide("impact"); }}
                          className="mono text-white/70 hover:text-[#3FC8E8] truncate text-[11px] block w-full text-left" title="Select this file">{cn.file_path}</button>
                      ))}
                    </div>
                  ))}
                </>}
              </div>
            )}
            {side === "dead" && (
              <div data-testid="arch-deadcode">
                {deadError ? <ErrorState message={deadError} onRetry={() => loadSidePanels()} testId="arch-dead-error" compact /> :
                !deadCode ? <div className="text-white/40 flex items-center gap-1.5" role="status"><Loader2Icon width={12} height={12} className="animate-spin" aria-hidden="true" />Analyzing…</div> :
                deadCode.count === 0 ? <div className="text-[#34C759]">No likely dead code detected.</div> :
                <>
                  <div className="text-white/60 mb-2">{deadCode.count} possibly-unused symbols.</div>
                  {deadCode.items.slice(0, 30).map((d, i) => (
                    <button key={i} data-testid={`dead-${i}`} onClick={() => { selectNode(d.node.id); setSide("impact"); }}
                      className={`w-full text-left border rounded-sm p-2 mb-1.5 transition-colors ${selectedNodeId === d.node.id ? "border-[#3FC8E8]/50 bg-[#3FC8E8]/5" : "border-white/10 hover:border-white/30"}`}>
                      <div className="flex items-center justify-between">
                        <div className="text-white/90 truncate mono text-[11px]">{d.node.qualified_name}</div>
                        <span className="text-[10px] mono text-[#FFB300]">{Math.round(d.confidence * 100)}%</span>
                      </div>
                      <div className="text-[10px] text-white/40 truncate">{d.node.file_path}:{d.node.start_line}</div>
                    </button>
                  ))}
                </>}
              </div>
            )}
            {side === "impact" && (
              <div data-testid="arch-impact">
                {!selectedNodeId ? <div className="text-white/40">Click a node in the graph to see impact analysis.</div> :
                impact?.error ? <ErrorState message={impact.message} onRetry={() => setImpactNonce((x) => x + 1)} testId="arch-impact-error" compact /> :
                !impact ? <div className="text-white/40 flex items-center gap-1.5"><Loader2Icon width={12} height={12} className="animate-spin" />Analyzing…</div> :
                <>
                  <div className="flex items-start justify-between mb-2">
                    <div className="min-w-0">
                      <div className="text-[10px] mono text-white/40 uppercase tracking-[0.16em]">Selected</div>
                      <div className="text-sm mono text-white truncate" title={selectedInfo?.label}>{selectedInfo?.label}</div>
                      <div className="text-[10px] text-white/40 truncate">{selectedInfo?.file}</div>
                    </div>
                    <button onClick={() => { clearSelection(); setImpact(null); }} aria-label="Clear selection" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm" data-testid="arch-clear-selection"><XIcon width={14} height={14} aria-hidden="true" /></button>
                  </div>
                  <div className="flex gap-1.5 mb-3">
                    <button data-testid="arch-trace-flow" onClick={traceFlow} className="flex-1 bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black text-xs py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px"><ZapIcon width={11} height={11} /> Trace flow</button>
                    <button data-testid="arch-view-graph" disabled={!nodeById.has(selectedNodeId)} onClick={() => setActiveTab("graph")}
                      className="flex-1 border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] disabled:opacity-40 text-white/70 text-xs py-1.5 rounded-sm flex items-center justify-center gap-1.5">
                      <NetworkIcon width={11} height={11} /> Graph
                    </button>
                    <button data-testid="arch-ask-chat" disabled={repo?.status !== "ready"} title="Ask about this symbol once AI indexing finishes"
                      onClick={() => askInChat(`Explain ${selectedInfo?.qualified_name || selectedInfo?.label} in ${selectedInfo?.file || "this repo"} — what does it do and why might it matter architecturally?`)}
                      className="flex-1 border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 text-xs py-1.5 rounded-sm flex items-center justify-center gap-1.5">
                      <MessageSquareTextIcon width={11} height={11} />
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 mb-3">
                    {[["callers", impact.summary.callers, "#FF9100"], ["callees", impact.summary.callees, "#2979FF"], ["deps", impact.summary.dependents, "#D500F9"]].map(([l, v, c]) => (
                      <div key={l} className="border border-white/10 rounded-sm p-2 text-center">
                        <div className="text-lg font-semibold" style={{ color: c, fontFamily: "Chivo" }}>{v}</div>
                        <div className="text-[9px] mono uppercase tracking-[0.14em] text-white/40">{l}</div>
                      </div>
                    ))}
                  </div>
                  {["callers", "callees", "dependents"].map((k) => (
                    impact[k]?.length > 0 && (
                      <div key={k} className="mb-2">
                        <div className="text-[10px] mono uppercase tracking-[0.16em] text-white/40 mb-1">{k}</div>
                        {impact[k].slice(0, 8).map((n) => (
                          <button key={n.id} data-testid={`impact-${k}-${n.id}`} onClick={() => selectNode(n.id)}
                            className="text-[11px] mono text-white/70 hover:text-[#3FC8E8] truncate block w-full text-left" title={n.qualified_name}>
                            · {n.qualified_name}
                          </button>
                        ))}
                      </div>
                    )
                  ))}
                </>}
              </div>
            )}
            {side === "flow" && (
              <div data-testid="arch-flow">
                {flow?.error ? (
                  <ErrorState message={flow.message} onRetry={traceFlow} testId="arch-flow-error" compact />
                ) : !flow ? (
                  <div className="text-white/40 flex items-center gap-1.5" role="status"><Loader2Icon width={12} height={12} className="animate-spin" aria-hidden="true" />Tracing…</div>
                ) : (
                  <>
                    <div className="text-white/80 mb-3">
                      Execution flow from <span className="mono text-[#3FC8E8]">{selectedInfo?.label}</span>: {flow.nodes.length} nodes, {flow.edges.length} edges within 3 hops.
                    </div>
                    <button data-testid="arch-flow-reset" onClick={() => { setSide("impact"); load(view); }}
                      className="w-full border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] text-white/70 text-xs py-1.5 rounded-sm flex items-center justify-center gap-1.5 transition-colors duration-150">
                      <RefreshCwIcon width={11} height={11} aria-hidden="true" /> Back to full {VIEWS.find((v) => v.k === view)?.label} view
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
