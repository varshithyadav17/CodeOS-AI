import { memo } from "react";
import { Handle, Position } from "reactflow";

import { NODE_COLORS } from "../../lib/graphLayout";
import "./graph.css";

// ReactFlow re-invokes every node component on most graph-level state
// changes (pan/zoom, sibling node updates); memoizing avoids re-rendering
// the hundreds of unaffected node cards when only one node's highlight
// flag changes.
function KGNodeView({ data }) {
  const color = NODE_COLORS[data.type] || "#3FC8E8";
  return (
    <div
      data-testid={`kg-node-${data.id}`}
      role="button"
      tabIndex={-1}
      aria-label={`${data.type} ${data.label}${data.highlight ? " (selected)" : ""}`}
      className={`code-map-node ${data.highlight ? "is-selected" : ""} ${data.related ? "is-related" : ""}`}
      style={{ "--node-color": color, opacity: data.dimmed ? 0.38 : 1 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "rgba(255,255,255,0.2)" }} />
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} aria-hidden="true" />
        <span className="text-[9px] mono uppercase tracking-[0.18em]" style={{ color }}>{data.type}</span>
        {data.hotspot && <span className="ml-auto text-amber-300 text-[8px]">HOTSPOT</span>}
      </div>
      <div className="mono text-[11px] mt-1 truncate" title={data.label}>{data.label}</div>
      {data.file && <div className="text-[10px] text-white/40 truncate mt-0.5">{data.file}</div>}
      {data.lines && <div className="code-map-node-lines">L{data.lines}</div>}
      <Handle type="source" position={Position.Right} style={{ background: "rgba(255,255,255,0.2)" }} />
    </div>
  );
}

export default memo(KGNodeView);
