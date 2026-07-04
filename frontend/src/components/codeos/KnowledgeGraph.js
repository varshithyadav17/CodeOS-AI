import { useEffect, useMemo, useRef } from "react";
import ReactFlow, { Background, Controls, MiniMap, useNodesState, useEdgesState, useReactFlow, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { Network } from "lucide-react";
import KGNodeView from "./KGNodeView";
import { useWorkspace } from "../../context/WorkspaceContext";
import { EmptyState } from "../ui/state";

const nodeTypes = { kg: KGNodeView };

// Radial layout: group by type, place around concentric circles. This is
// the expensive part (trig for every node) and depends only on the graph
// shape — NOT on which node happens to be selected — so it's memoized
// separately from highlight state (below). Previously this and the
// highlight flag were computed together, which meant every selection
// change (a frequent interaction) recomputed the layout of every node for
// no reason.
function layoutPositions(nodes) {
  const types = {};
  nodes.forEach((n) => { (types[n.type] ||= []).push(n); });
  const groups = Object.keys(types);
  const positioned = {};
  const radiusStep = 280;
  groups.forEach((g, gi) => {
    const r = (gi + 1) * radiusStep;
    const arr = types[g];
    arr.forEach((n, i) => {
      const a = (i / Math.max(arr.length, 1)) * Math.PI * 2;
      positioned[n.id] = { x: Math.cos(a) * r, y: Math.sin(a) * r };
    });
  });
  return positioned;
}

function GraphInner({ nodes, edges }) {
  const { selectedNodeId, selectNode } = useWorkspace();

  // Expensive, selection-independent: only recomputes when the graph data
  // itself changes.
  const positions = useMemo(() => layoutPositions(nodes || []), [nodes]);

  // Cheap, selection-dependent: a plain map over already-positioned nodes.
  const flowNodes = useMemo(
    () => (nodes || []).map((n) => ({
      id: n.id,
      type: "kg",
      position: positions[n.id] || { x: 0, y: 0 },
      data: { id: n.id, type: n.type, label: n.name, file: n.file_path, highlight: n.id === selectedNodeId },
    })),
    [nodes, positions, selectedNodeId]
  );

  const flowEdges = useMemo(
    () => (edges || []).map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      label: e.type,
      labelStyle: { fill: "rgba(255,255,255,0.5)", fontSize: 9, fontFamily: "JetBrains Mono" },
      labelBgPadding: [2, 2],
      labelBgStyle: { fill: "#0A0A0A" },
      style: {
        stroke: e.source_id === selectedNodeId || e.target_id === selectedNodeId ? "#3FC8E8" : "rgba(255,255,255,0.15)",
        strokeWidth: e.source_id === selectedNodeId || e.target_id === selectedNodeId ? 2 : 1,
        transition: "stroke 0.2s ease",
      },
    })),
    [edges, selectedNodeId]
  );

  const [n, setN, onNodesChange] = useNodesState(flowNodes);
  const [e, setE, onEdgesChange] = useEdgesState(flowEdges);
  const rf = useReactFlow();
  const lastCentered = useRef(null);

  useEffect(() => { setN(flowNodes); setE(flowEdges); }, [flowNodes, flowEdges, setN, setE]);

  // When the shared selection changes (from Files, Timeline, Architecture,
  // Chat context chips, etc.) and the node is present in this graph view,
  // smoothly re-center on it so the click always feels connected.
  useEffect(() => {
    if (!selectedNodeId || selectedNodeId === lastCentered.current) return;
    const node = flowNodes.find((fn) => fn.id === selectedNodeId);
    if (node && rf) {
      rf.setCenter(node.position.x + 90, node.position.y + 30, { zoom: 0.9, duration: 500 });
      lastCentered.current = selectedNodeId;
    }
  }, [selectedNodeId, flowNodes, rf]);

  const onNodeClick = (_, node) => selectNode(node.id);

  if ((nodes || []).length === 0) {
    return (
      <EmptyState
        icon={Network}
        title="No graph nodes to show."
        subtitle="This can happen for very small or unparsable repositories."
        testId="knowledge-graph-empty"
      />
    );
  }

  return (
    <div className="w-full h-[600px] glass-panel-soft border border-white/10 rounded-xl dot-grid" data-testid="knowledge-graph">
      <ReactFlow
        nodes={n}
        edges={e}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(255,255,255,0.06)" gap={20} />
        <Controls className="rf-controls-glass" />
        <MiniMap
          nodeColor={(node) => ({ file: "#D500F9", class: "#2979FF", function: "#FF9100", method: "#FF9100" }[node.data?.type] || "#3FC8E8")}
          maskColor="rgba(0,0,0,0.7)"
          style={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)" }}
        />
      </ReactFlow>
    </div>
  );
}

export default function KnowledgeGraph({ nodes, edges }) {
  return (
    <ReactFlowProvider>
      <GraphInner nodes={nodes} edges={edges} />
    </ReactFlowProvider>
  );
}
