// Deterministic layouts preserve dependency direction and keep cycles together.
export const NODE_COLORS = { file: '#a99cff', class: '#69aaff', function: '#5cdbc7', method: '#5cdbc7', variable: '#e7bc79' };
export const EDGE_COLORS = { CALLS: '#5cdbc7', IMPORTS: '#a99cff', CONTAINS: '#4c647b', INHERITS: '#69aaff' };
export function dependencyPositions(nodes, edges) {
  const ids = nodes.map(n => n.id).sort(), links = new Map(ids.map(id => [id, []]));
  for (const e of edges) if (links.has(e.source_id) && links.has(e.target_id)) links.get(e.source_id).push(e.target_id);
  let cursor = 0;
  const index = new Map(), low = new Map(), stack = [], onStack = new Set(), components = [];
  function visit(id) {
    index.set(id, cursor); low.set(id, cursor++); stack.push(id); onStack.add(id);
    for (const target of links.get(id)) {
      if (!index.has(target)) { visit(target); low.set(id, Math.min(low.get(id), low.get(target))); }
      else if (onStack.has(target)) low.set(id, Math.min(low.get(id), index.get(target)));
    }
    if (low.get(id) === index.get(id)) {
      const group = []; let member;
      do { member = stack.pop(); onStack.delete(member); group.push(member); } while (member !== id);
      components.push(group.sort());
    }
  }
  ids.forEach(id => { if (!index.has(id)) visit(id); });
  const owner = new Map();
  components.forEach((group, i) => group.forEach(id => owner.set(id, i)));
  const outgoing = components.map(() => new Set()), indegree = components.map(() => 0), rank = components.map(() => 0);
  for (const [id, targets] of links) for (const target of targets) {
    const a = owner.get(id), b = owner.get(target);
    if (a !== b && !outgoing[a].has(b)) { outgoing[a].add(b); indegree[b]++; }
  }
  const queue = indegree.flatMap((degree, i) => degree === 0 ? [i] : []);
  for (let i = 0; i < queue.length; i++) for (const next of outgoing[queue[i]]) {
    rank[next] = Math.max(rank[next], rank[queue[i]] + 1);
    if (--indegree[next] === 0) queue.push(next);
  }
  const incident = new Set();
  for (const [id, targets] of links) for (const target of targets) { incident.add(id); incident.add(target); }
  const levels = new Map(), positions = {}, isolated = [];
  for (const component of queue) for (const id of components[component]) {
    if (!incident.has(id)) { isolated.push(id); continue; }
    const level = rank[component];
    if (!levels.has(level)) levels.set(level, []);
    levels.get(level).push(id);
  }
  const maxRows = Math.max(0, ...[...levels.values()].map(group => group.length));
  for (const [level, group] of levels) group.forEach((id, row) => {
    // A single column per dependency rank keeps peer nodes out of each
    // other's horizontal edge paths. Center narrower ranks on their peers.
    positions[id] = { x: level * 380, y: (row + (maxRows - group.length) / 2) * 130 };
  });
  // Independent symbols have no direction to preserve: pack them below the
  // connected graph instead of creating one very tall dependency column.
  isolated.forEach((id, i) => {
    positions[id] = { x: (i % 5) * 250, y: (maxRows ? maxRows * 130 + 120 : 0) + Math.floor(i / 5) * 130 };
  });
  return positions;
}
export function filePositions(nodes) {
  const groups = new Map(), positions = {};
  for (const node of nodes) {
    const key = node.file_path || 'Other symbols';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(node);
  }
  const columns = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(groups.size))));
  let column = 0, y = 0, height = 0;
  for (const [, group] of [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const file = group.find(n => n.type === 'file');
    if (file) positions[file.id] = { x: column * 800 + 250, y };
    const symbols = group.filter(n => n !== file);
    symbols.forEach((n, i) => { positions[n.id] = { x: column * 800 + (i % 3) * 250, y: y + (file ? 130 : 0) + Math.floor(i / 3) * 130 }; });
    height = Math.max(height, 180 + (file ? 130 : 0) + Math.ceil(symbols.length / 3) * 130);
    if (++column === columns) { column = 0; y += height; height = 0; }
  }
  return positions;
}
export function connectedIds(id, edges) {
  const ids = new Set(id ? [id] : []);
  for (const e of edges) {
    if (e.source_id === id) ids.add(e.target_id);
    if (e.target_id === id) ids.add(e.source_id);
  }
  return ids;
}
export function graphEdges(edges, selectedId) {
  return edges.map(e => {
    const active = e.source_id === selectedId || e.target_id === selectedId;
    const color = e.metadata?.in_cycle ? '#ff7979' : EDGE_COLORS[e.type] || '#7894ac';
    return { id: e.id, source: e.source_id, target: e.target_id, type: 'smoothstep',
      label: active ? e.type : undefined, labelStyle: { fill: color, fontSize: 9 },
      labelBgStyle: { fill: '#0b1724', fillOpacity: 0.98 }, labelBgPadding: [5, 3],
      markerEnd: { type: 'arrowclosed', color, width: 14, height: 14 },
      style: { stroke: color, strokeWidth: active ? 2 : 1.2, opacity: selectedId && !active ? 0.18 : active ? 1 : 0.5 },
    };
  });
}
