import { useEffect, useMemo, useCallback, memo } from "react";
import ReactFlow, { Background, Controls, MiniMap, useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";
import { useWorkspace } from "../../context/WorkspaceContext";
import NetworkIcon from "../../assets/icons/network.svg?react";
import { EmptyState, ErrorState } from "../../components/EmptyState";
import KGNodeView from "./KGNodeView";
import Skeleton from "../../components/Skeleton";

const nodeTypes = { kg: KGNodeView };

function buildFlowNodes(nodes, selectedNodeId, highlightedIds = new Set()) {
  const groups = new Map();
  for (const node of nodes) {
    if (!groups.has(node.file_path)) groups.set(node.file_path, []);
    groups.get(node.file_path).push(node);
  }
  const positions = new Map();
  const columns = Math.max(1, Math.ceil(Math.sqrt(groups.size)));
  let column = 0, rowY = 0, rowHeight = 0;
  for (const group of groups.values()) {
    const file = group.find((n) => n.type === "file");
    if (file) positions.set(file.id, { x: column * 720 + 220, y: rowY });
    const symbols = group.filter((n) => n !== file);
    symbols.forEach((n, i) => positions.set(n.id, { x: column * 720 + (i % 3) * 220, y: rowY + 110 + Math.floor(i / 3) * 100 }));
    rowHeight = Math.max(rowHeight, 200 + Math.ceil(symbols.length / 3) * 100);
    column += 1;
    if (column === columns) { column = 0; rowY += rowHeight; rowHeight = 0; }
  }
  return nodes.map((n) => ({
    id: n.id,
    type: "kg",
    position: n.position || positions.get(n.id),
    data: {
      id: n.id,
      type: n.type,
      label: n.name || n.qualified_name,
      file: n.file_path,
      highlight: n.id === selectedNodeId || highlightedIds.has(n.id),
    },
  }));
}

function buildFlowEdges(edges) {
  return edges.map((e) => ({
    id: e.id,
    source: e.source_id,
    target: e.target_id,
    label: e.type,
    labelStyle: { fill: "rgba(255,255,255,0.5)", fontSize: 9, fontFamily: "JetBrains Mono" },
    labelBgPadding: [2, 2],
    labelBgStyle: { fill: "#0A0A0A" },
    style: { stroke: "rgba(255,255,255,0.18)", strokeWidth: 1.2 },
  }));
}

const KnowledgeGraph = memo(function KnowledgeGraph() {
  const { graph, graphLoading, graphError, loadGraphPage, repoLoading, repoLoadError, selectedNodeId, selectNode, highlightPaths, fileNodeByPath } = useWorkspace();
  const nodes = useMemo(() => graph?.nodes || [], [graph]);
  const edges = useMemo(() => graph?.edges || [], [graph]);
  const loading = repoLoading;
  const error = repoLoadError;

  // Derive the set of highlighted node IDs from the cross-panel highlighted
  // file paths (set by the Timeline hotspot analysis).
  const highlightedIds = useMemo(() => {
    const ids = new Set();
    highlightPaths.forEach((p) => {
      const n = fileNodeByPath.get(p);
      if (n) ids.add(n.id);
    });
    return ids;
  }, [highlightPaths, fileNodeByPath]);

  const flowNodes = useMemo(() => buildFlowNodes(nodes, selectedNodeId, highlightedIds), [nodes, selectedNodeId, highlightedIds]);
  const flowEdges = useMemo(() => buildFlowEdges(edges), [edges]);

  const [n, setN, onNodesChange] = useNodesState(flowNodes);
  const [e, setE, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => { setN(flowNodes); }, [flowNodes, setN]);
  useEffect(() => { setE(flowEdges); }, [flowEdges, setE]);

  const onNodeClick = useCallback((_, node) => { selectNode(node.id); }, [selectNode]);

  if (loading) return <Skeleton className="h-[600px]" />;
  if (error) return <ErrorState message={error} testId="graph-error" />;
  if (nodes.length === 0) return (
    <EmptyState
      icon={NetworkIcon}
      title="No knowledge graph yet."
      subtitle="This repository is still being ingested, or the graph is empty."
      testId="graph-empty"
    />
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-xs text-white/60" aria-live="polite">
        <span data-testid="graph-page-status">Nodes {(graph.offset || 0) + 1}–{(graph.offset || 0) + nodes.length}{graph.total != null ? ` of ${graph.total}` : ""}</span>
        <div className="ml-auto flex gap-2">
          <button data-testid="graph-previous" disabled={graphLoading || !graph.offset} onClick={() => loadGraphPage(Math.max(0, graph.offset - graph.limit))} className="border border-white/20 rounded px-3 py-1 disabled:opacity-30">Previous</button>
          <button data-testid="graph-next" disabled={graphLoading || !graph.has_more} onClick={() => loadGraphPage((graph.offset || 0) + graph.limit)} className="border border-white/20 rounded px-3 py-1 disabled:opacity-30">{graphLoading ? "Loading…" : "Next"}</button>
        </div>
      </div>
      {graphError && <p className="text-sm text-red-400" role="alert">{graphError}</p>}
      {graph.edges_truncated && <p className="text-xs text-white/50">This dense graph page shows the first 10,000 relationships.</p>}
    <div className="glass-panel-soft border border-white/10 rounded-xl dot-grid h-[600px] relative" data-testid="knowledge-graph">
      <ReactFlow
        nodes={n}
        edges={e}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        minZoom={0.05}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(255,255,255,0.05)" gap={20} />
        <Controls className="rf-controls-glass" />
        <MiniMap maskColor="rgba(0,0,0,0.7)" style={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)" }} />
      </ReactFlow>
    </div>
    </div>
  );
});

export default KnowledgeGraph;
