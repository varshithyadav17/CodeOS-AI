import { createContext, useCallback, useContext, useMemo, useState } from "react";

const WorkspaceContext = createContext(null);

/**
 * Single shared state for the Repository Detail "AI Engineering Workspace".
 *
 * This does NOT call the backend itself — it holds selection/navigation
 * state (which file, which graph node, which tab, a pending chat prompt,
 * a set of "highlighted" files) so that every panel (Chat, Knowledge Graph,
 * Architecture, Timeline, Reviews, Docs, Files) can read and write the same
 * selection instead of maintaining disconnected local state.
 *
 * Data (graph/files/repo) is still fetched by RepoDetail exactly as before —
 * this only adds a coordination layer on top of existing API responses.
 */
export function WorkspaceProvider({ repoId, repo, graph, files, children }) {
  const [activeTab, setActiveTab] = useState("chat");
  const [selectedFilePath, setSelectedFilePath] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [highlightPaths, setHighlightPathsState] = useState(() => new Set());
  const [pendingChatPrompt, setPendingChatPrompt] = useState(null);

  // ---- lookup indexes built once per graph fetch --------------------------
  const nodeById = useMemo(() => {
    const m = new Map();
    (graph?.nodes || []).forEach((n) => m.set(n.id, n));
    return m;
  }, [graph]);

  const fileNodeByPath = useMemo(() => {
    const m = new Map();
    (graph?.nodes || []).forEach((n) => {
      if (n.type === "file") m.set(n.file_path, n);
    });
    return m;
  }, [graph]);

  const knownFilePaths = useMemo(() => new Set((files || []).map((f) => f.path)), [files]);

  // ---- shared actions -------------------------------------------------------

  /** Select a file by path. Also resolves + selects its graph "file" node
   * if one exists, so Graph/Architecture stay in sync. */
  const selectFile = useCallback(
    (path, opts = {}) => {
      if (!path) return;
      setSelectedFilePath(path);
      const node = fileNodeByPath.get(path);
      setSelectedNodeId(node ? node.id : null);
      if (opts.tab) setActiveTab(opts.tab);
    },
    [fileNodeByPath]
  );

  /** Select a graph node by id. Also resolves + selects its file path if
   * the node carries one, so Files/Timeline stay in sync. */
  const selectNode = useCallback(
    (nodeId, opts = {}) => {
      if (!nodeId) return;
      setSelectedNodeId(nodeId);
      const node = nodeById.get(nodeId);
      if (node?.file_path) setSelectedFilePath(node.file_path);
      if (opts.tab) setActiveTab(opts.tab);
    },
    [nodeById]
  );

  const clearSelection = useCallback(() => {
    setSelectedFilePath(null);
    setSelectedNodeId(null);
  }, []);

  /** Highlight a set of file paths (e.g. Timeline hotspots) so the Files
   * list can flag them even though nothing is "selected". */
  const setHighlightPaths = useCallback((paths) => {
    setHighlightPathsState(new Set(paths || []));
  }, []);

  /** Send a prompt to the Chat panel and switch to it. ChatPanel consumes
   * `pendingChatPrompt` and clears it once applied. */
  const askInChat = useCallback((text) => {
    setPendingChatPrompt({ text, nonce: Date.now() });
    setActiveTab("chat");
  }, []);

  const clearPendingChatPrompt = useCallback(() => setPendingChatPrompt(null), []);

  const value = useMemo(
    () => ({
      repoId,
      repo,
      graph,
      files,
      knownFilePaths,
      nodeById,
      fileNodeByPath,
      activeTab,
      setActiveTab,
      selectedFilePath,
      selectedNodeId,
      selectFile,
      selectNode,
      clearSelection,
      highlightPaths,
      setHighlightPaths,
      pendingChatPrompt,
      clearPendingChatPrompt,
      askInChat,
    }),
    [
      repoId,
      repo,
      graph,
      files,
      knownFilePaths,
      nodeById,
      fileNodeByPath,
      activeTab,
      selectedFilePath,
      selectedNodeId,
      selectFile,
      selectNode,
      clearSelection,
      highlightPaths,
      setHighlightPaths,
      pendingChatPrompt,
      clearPendingChatPrompt,
      askInChat,
    ]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace() must be used within a <WorkspaceProvider>");
  }
  return ctx;
}
