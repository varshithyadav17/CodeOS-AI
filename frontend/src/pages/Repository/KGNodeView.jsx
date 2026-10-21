import { memo } from "react";
import { Handle, Position } from "reactflow";

const COLORS = {
  file: "#D500F9",
  class: "#2979FF",
  function: "#FF9100",
  method: "#FF9100",
  variable: "#00E676",
};

// ReactFlow re-invokes every node component on most graph-level state
// changes (pan/zoom, sibling node updates); memoizing avoids re-rendering
// the hundreds of unaffected node cards when only one node's highlight
// flag changes.
function KGNodeView({ data }) {
  const color = COLORS[data.type] || "#3FC8E8";
  return (
    <div
      data-testid={`kg-node-${data.id}`}
      role="button"
      tabIndex={-1}
      aria-label={`${data.type} ${data.label}${data.highlight ? " (selected)" : ""}`}
      className="graph-node-surface border rounded-sm px-3 py-2 min-w-[140px] max-w-[220px] text-white text-xs shadow-lg transition-[border-color,box-shadow] duration-200"
      style={{ borderColor: data.highlight ? "#3FC8E8" : "rgba(255,255,255,0.15)", boxShadow: data.highlight ? "0 0 12px rgba(63, 200, 232,0.35)" : "none" }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "rgba(255,255,255,0.2)" }} />
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} aria-hidden="true" />
        <span className="text-[9px] mono uppercase tracking-[0.18em]" style={{ color }}>{data.type}</span>
      </div>
      <div className="mono text-[11px] mt-1 truncate" title={data.label}>{data.label}</div>
      {data.file && <div className="text-[10px] text-white/40 truncate mt-0.5">{data.file}</div>}
      <Handle type="source" position={Position.Right} style={{ background: "rgba(255,255,255,0.2)" }} />
    </div>
  );
}

export default memo(KGNodeView);
