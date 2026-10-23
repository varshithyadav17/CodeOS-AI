import { useEffect, useMemo, useCallback, useRef, useState, memo } from 'react';
import ReactFlow, { Background, Controls, MiniMap, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import { useWorkspace } from '../../context/WorkspaceContext';
import { connectedIds, dependencyPositions, filePositions, graphEdges, NODE_COLORS } from '../../lib/graphLayout';
import NetworkIcon from '../../assets/icons/network.svg?react';
import SearchIcon from '../../assets/icons/search.svg?react';
import { EmptyState, ErrorState } from '../../components/EmptyState';
import KGNodeView from './KGNodeView';
import Skeleton from '../../components/Skeleton';
import './graph.css';
const nodeTypes = { kg: KGNodeView };
const KnowledgeGraph = memo(function KnowledgeGraph() {
  const { repo, graph, graphLoading, graphError, loadGraphPage, repoLoading, repoLoadError,
    selectedNodeId, selectNode, selectFile, clearSelection, askInChat, highlightPaths } = useWorkspace();
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('all');
  const [relation, setRelation] = useState('all');
  const [layout, setLayout] = useState('files');
  const [focus, setFocus] = useState(false);
  const [instance, setInstance] = useState(null);
  const previousLayout = useRef(null);
  const nodes = useMemo(() => graph?.nodes || [], [graph]);
  const edges = useMemo(() => graph?.edges || [], [graph]);
  const selected = nodes.find(node => node.id === selectedNodeId);
  const neighborhood = useMemo(() => connectedIds(selectedNodeId, edges), [selectedNodeId, edges]);
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filteredEdges = edges.filter(e => relation === 'all' || e.type === relation);
    const related = new Set(filteredEdges.flatMap(e => [e.source_id, e.target_id]));
    const keep = nodes.filter(n => (kind === 'all' || n.type === kind)
      && (!q || `${n.name} ${n.qualified_name} ${n.file_path}`.toLowerCase().includes(q))
      && (!focus || !selected || neighborhood.has(n.id)) && (relation === 'all' || related.has(n.id)));
    const ids = new Set(keep.map(n => n.id));
    return { nodes: keep, edges: filteredEdges.filter(e => ids.has(e.source_id) && ids.has(e.target_id)) };
  }, [search, nodes, edges, kind, relation, focus, selected, neighborhood]);
  const positions = useMemo(() => layout === 'files' ? filePositions(visible.nodes) : dependencyPositions(visible.nodes, visible.edges), [visible, layout]);
  const layoutKey = JSON.stringify(positions);
  const flowNodes = useMemo(() => visible.nodes.map(node => ({ id: node.id, type: 'kg', position: positions[node.id],
    data: { id: node.id, type: node.type, label: node.name || node.qualified_name, file: node.file_path,
      language: node.language, lines: node.start_line ? `${node.start_line}–${node.end_line || node.start_line}` : null,
      highlight: node.id === selectedNodeId, related: selected && neighborhood.has(node.id),
      hotspot: highlightPaths.has(node.file_path), dimmed: selected && !neighborhood.has(node.id) },
  })), [visible.nodes, positions, selectedNodeId, selected, neighborhood, highlightPaths]);
  const flowEdges = useMemo(() => graphEdges(visible.edges, selected?.id), [visible.edges, selected?.id]);
  const [n, setN, onNodesChange] = useNodesState(flowNodes);
  const [e, setE, onEdgesChange] = useEdgesState(flowEdges);
  useEffect(() => {
    const preserve = previousLayout.current === layoutKey;
    previousLayout.current = layoutKey;
    setN(current => {
      const byId = new Map(current.map(node => [node.id, node]));
      return flowNodes.map(node => preserve && byId.has(node.id) ? { ...node, position: byId.get(node.id).position } : node);
    });
  }, [flowNodes, layoutKey, setN]);
  useEffect(() => { setE(flowEdges); }, [flowEdges, setE]);
  useEffect(() => {
    const timer = setTimeout(() => instance?.fitView({ padding: 0.18, maxZoom: 1.1 }), 80);
    return () => clearTimeout(timer);
  }, [instance, layoutKey]);
  const onNodeClick = useCallback((_, node) => selectNode(node.id), [selectNode]);
  const reset = () => { setSearch(''); setKind('all'); setRelation('all'); setFocus(false); };
  const incoming = edges.filter(edge => edge.target_id === selectedNodeId);
  const outgoing = edges.filter(edge => edge.source_id === selectedNodeId);
  const neighbors = nodes.filter(node => node.id !== selectedNodeId && neighborhood.has(node.id));
  if (repoLoading) return <Skeleton className="h-[600px]" />;
  if (repoLoadError) return <ErrorState message={repoLoadError} testId="graph-error" />;
  if (!nodes.length) return <EmptyState icon={NetworkIcon} title="No knowledge graph yet." subtitle="The graph will appear after source parsing finishes." testId="graph-empty" />;
  return <section className="code-map" aria-label="Repository code map">
    <header className="code-map-heading">
      <div className="code-map-title"><NetworkIcon width={22} height={22} aria-hidden="true" /><div><h2>Code map</h2><p>Explore the structure. Follow the connections.</p></div></div>
      <div className="code-map-counter" aria-live="polite"><strong data-testid="graph-visible-count">{visible.nodes.length}</strong> symbols <span>/</span> {visible.edges.length} connections</div>
    </header>
    <div className="code-map-toolbar">
      <label className="code-map-search"><SearchIcon width={15} height={15} aria-hidden="true" /><input aria-label="Search graph page" data-testid="graph-search" placeholder="Find a symbol or file on this page…" value={search} onChange={event => setSearch(event.target.value)} /></label>
      <label className="sr-only" htmlFor="graph-node-type">Symbol type</label>
      <select id="graph-node-type" data-testid="graph-node-type" value={kind} onChange={event => setKind(event.target.value)}><option value="all">All symbols</option>{[...new Set(nodes.map(node => node.type))].sort().map(type => <option key={type} value={type}>{type}</option>)}</select>
      <label className="sr-only" htmlFor="graph-relationship">Relationship type</label>
      <select id="graph-relationship" value={relation} onChange={event => setRelation(event.target.value)}><option value="all">All connections</option>{[...new Set(edges.map(edge => edge.type))].sort().map(type => <option key={type}>{type}</option>)}</select>
      <div className="code-map-layout" aria-label="Graph layout"><button aria-pressed={layout === 'files'} onClick={() => setLayout('files')}>By file</button><button data-testid="graph-layout-dependencies" aria-pressed={layout === 'dependencies'} onClick={() => setLayout('dependencies')}>Dependencies →</button></div>
    </div>
    <div className="code-map-workspace">
      <div className="code-map-canvas" data-testid="knowledge-graph">
        <div className="code-map-canvas-caption"><span className="code-map-beacon" />{layout === 'files' ? 'FILE CLUSTERS' : 'DEPENDENCY LAYERS'}<span>{focus && selected ? 'NEIGHBORHOOD' : 'PAGE VIEW'}</span></div>
        <ReactFlow nodes={n} edges={e} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} onInit={setInstance} fitView minZoom={0.03} maxZoom={1.8} nodesConnectable={false} proOptions={{ hideAttribution: true }}>
          <Background color="#20384a" gap={24} size={1} />
          <Controls className="rf-controls-glass" showInteractive={false} />
          <MiniMap nodeColor={node => NODE_COLORS[node.data.type] || '#5cdbc7'} nodeStrokeWidth={0} maskColor="rgba(5,12,21,0.7)" style={{ background: '#0c1b29', border: '1px solid #274051' }} pannable zoomable />
        </ReactFlow>
        {!visible.nodes.length && <div className="code-map-no-results" role="status"><strong>No matching symbols on this page</strong><button onClick={reset} data-testid="graph-reset">Reset filters</button></div>}
        <div className="code-map-legend">{Object.entries(NODE_COLORS).filter(([type]) => nodes.some(node => node.type === type)).map(([type, color]) => <span key={type}><i style={{ background: color }} />{type}</span>)}</div>
      </div>
      <aside className="code-map-inspector" aria-label="Symbol inspector" data-testid="graph-inspector">
        {selected ? <>
          <div className="code-map-eyebrow">SYMBOL INSPECTOR <button aria-label="Clear graph selection" onClick={() => { clearSelection(); setFocus(false); }}>×</button></div>
          <span className="code-map-type" style={{ color: NODE_COLORS[selected.type] || '#5cdbc7' }}>{selected.type}</span>
          <h3>{selected.name || selected.qualified_name}</h3><p className="code-map-path">{selected.file_path}</p>
          <p className="code-map-meta">{selected.language}{selected.start_line ? ` · Lines ${selected.start_line}–${selected.end_line || selected.start_line}` : ''}</p>
          <div className="code-map-metrics"><div><strong>{incoming.length}</strong>Incoming</div><div><strong>{outgoing.length}</strong>Outgoing</div></div>
          <button className="code-map-primary" data-testid="graph-focus" aria-pressed={focus} onClick={() => { setSearch(''); setKind('all'); setRelation('all'); setFocus(!focus); }}>{focus ? 'Show full page' : 'Focus connections'}</button>
          {selected.file_path && <button className="code-map-action" data-testid="graph-open-source" onClick={() => selectFile(selected.file_path, { tab: 'files' })}>Open source ↗</button>}
          <button className="code-map-action" disabled={repo?.status !== 'ready'} title={repo?.status === 'ready' ? 'Ask about this symbol' : 'Available when AI indexing finishes'} onClick={() => askInChat(`Explain ${selected.qualified_name || selected.name} in ${selected.file_path} and its relationships.`)}>Ask AI about this symbol ↗</button>
          <div className="code-map-eyebrow code-map-neighbors">CONNECTED SYMBOLS · THIS PAGE</div>
          {neighbors.slice(0, 12).map(node => <button className="code-map-neighbor" key={node.id} onClick={() => selectNode(node.id)} title={node.file_path}><i style={{ background: NODE_COLORS[node.type] || '#5cdbc7' }} /><span>{node.name || node.qualified_name}</span><span>→</span></button>)}
          {!neighbors.length && <p className="code-map-hint">No connected symbols on this page. Architecture offers call and dependency views across the repository.</p>}
          {neighbors.length > 12 && <p className="code-map-hint">Showing 12 of {neighbors.length} connected symbols. Focus the map to explore all of them.</p>}
        </> : <div className="code-map-welcome"><div className="code-map-radar"><NetworkIcon width={32} height={32} aria-hidden="true" /></div><div className="code-map-eyebrow">YOUR CODE, CONNECTED</div><h3>Select a symbol</h3><p>Inspect its incoming and outgoing connections, follow a dependency, or jump into the source.</p><div className="code-map-help"><span>Scroll / pinch</span><strong>Zoom</strong><span>Drag the canvas</span><strong>Pan</strong><span>Select a symbol</span><strong>Inspect</strong></div><p className="code-map-hint">Arrows show relationship direction. Connections are derived from static source analysis.</p></div>}
      </aside>
    </div>
    <footer className="code-map-footer">
      <span data-testid="graph-page-status" aria-live="polite">Nodes {(graph.offset || 0) + 1}–{(graph.offset || 0) + nodes.length}{graph.total != null ? ` of ${graph.total}` : ''}</span>
      <span className="code-map-page-hint">Filters and connections apply to this page.</span>
      {(search || kind !== 'all' || relation !== 'all' || focus) && <button onClick={reset}>Reset view</button>}
      <div><button data-testid="graph-previous" disabled={graphLoading || !graph.offset} onClick={() => { reset(); loadGraphPage(Math.max(0, graph.offset - graph.limit)); }}>Previous</button><button data-testid="graph-next" disabled={graphLoading || !graph.has_more} onClick={() => { reset(); loadGraphPage((graph.offset || 0) + graph.limit); }}>{graphLoading ? 'Loading…' : 'Next →'}</button></div>
    </footer>
    {graphError && <p className="p-3 text-sm text-red-400" role="alert">{graphError}</p>}
    {graph.edges_truncated && <p className="p-3 text-xs text-white/50">This dense page shows its first 10,000 relationships.</p>}
  </section>;
});
export default KnowledgeGraph;
