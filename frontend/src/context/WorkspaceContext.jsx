import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { hasParsedWorkspace } from "../lib/repositoryStatus";

const WorkspaceContext = createContext(null);

/**
 * Single source of truth for repository state across the app: the
 * repositories list (Repositories page), the currently-open repo's
 * detail/graph/files (Repository detail page), and cross-panel selection
 * state within a repo's workspace (which file, which graph node, which
 * tab, a pending chat prompt, a set of "highlighted" files).
 *
 * Mounted once at the app root so it survives route changes — this is
 * what lets e.g. Memory's "Open in workspace" link and the Repositories
 * list share fetch/CRUD logic with the Repository detail page instead of
 * each page re-implementing its own fetching.
 */
export function WorkspaceProvider({ children }) {
  // ---- Repositories list (Repositories page) --------------------------
  const [repositories, setRepositories] = useState([]);
  const [reposLoading, setReposLoading] = useState(true);
  const [reposError, setReposError] = useState(null);
  const repoInFlight = useRef(new Set()); // repo ids with an optimistic action pending
  const openedRepo = useRef(null);

  const loadRepositories = useCallback(async () => {
    const r = await api.get("/repos");
    setRepositories(r.data);
    setReposError(null);
    return r.data;
  }, []);

  const refreshRepositories = useCallback(async () => {
    setReposLoading(true);
    try {
      await loadRepositories();
    } catch (e) {
      setReposError(e?.response?.data?.detail || "Failed to load repositories.");
    } finally {
      setReposLoading(false);
    }
  }, [loadRepositories]);

  const addGithubRepo = useCallback(async (url, branch, token) => {
    const placeholder = {
      id: `optimistic-${Date.now()}`,
      name: url.split("/").pop()?.replace(/\.git$/, "") || url,
      status: "queued",
      progress: 0,
      message: "Queued for ingestion…",
      source: "github",
      source_url: url,
      branch: branch || null,
    };
    setRepositories((rs) => [...rs, placeholder]);
    try {
      await api.post("/repos/github", { url, branch: branch || null, token: token || null });
    } catch (err) {
      // POST failed — remove the placeholder so the list stays accurate.
      setRepositories((rs) => rs.filter((r) => r.id !== placeholder.id));
      throw err;
    }
    // Refresh silently; if it fails the placeholder stays visible until
    // the next polling tick rather than disappearing and confusing the user.
    loadRepositories().catch(() => {});
  }, [loadRepositories]);

  const uploadZipRepo = useCallback(async (file) => {
    const placeholder = {
      id: `optimistic-${Date.now()}`,
      name: file.name.replace(/\.zip$/i, ""),
      status: "queued",
      progress: 0,
      message: "Queued for ingestion…",
      source: "upload",
      source_url: null,
      branch: null,
    };
    setRepositories((rs) => [...rs, placeholder]);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("name", file.name.replace(/\.zip$/i, ""));
      await api.post("/repos/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
    } catch (err) {
      // POST failed — remove the placeholder so the list stays accurate.
      setRepositories((rs) => rs.filter((r) => r.id !== placeholder.id));
      throw err;
    }
    // Refresh silently; if it fails the placeholder stays visible until
    // the next polling tick rather than disappearing and confusing the user.
    loadRepositories().catch(() => {});
  }, [loadRepositories]);

  const deleteRepo = useCallback(async (id) => {
    if (repoInFlight.current.has(id)) return;
    repoInFlight.current.add(id);
    try {
      await api.delete(`/repos/${id}`);
      await loadRepositories();
    } finally { repoInFlight.current.delete(id); }
  }, [loadRepositories]);

  const reingestRepo = useCallback(async (id) => {
    if (repoInFlight.current.has(id)) return;
    repoInFlight.current.add(id);
    try {
      await api.post(`/repos/${id}/reingest`);
      if (openedRepo.current?.id === id) openedRepo.current.partsStarted = false;
      setRepositories((rs) => rs.map((r) => r.id === id ? { ...r, status: "queued", progress: 0, message: "Analysis queued" } : r));
      setRepo((r) => r?.id === id ? { ...r, status: "queued", progress: 0, message: "Analysis queued" } : r);
      await loadRepositories();
    } finally { repoInFlight.current.delete(id); }
  }, [loadRepositories]);

  // ---- Current repo detail (Repository detail page) --------------------
  const [currentRepoId, setCurrentRepoId] = useState(null);
  const [repo, setRepo] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState(null);
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState(null);
  const [repoLoading, setRepoLoading] = useState(true);
  const [repoLoadError, setRepoLoadError] = useState(null);

  // ---- Selection state (Repository workspace panels) --------------------
  const [activeTab, setActiveTab] = useState("chat");
  const [selectedFilePath, setSelectedFilePath] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [highlightPaths, setHighlightPathsState] = useState(() => new Set());
  const [pendingChatPrompt, setPendingChatPrompt] = useState(null);

  const resetSelection = useCallback(() => {
    setActiveTab("chat");
    setSelectedFilePath(null);
    setSelectedNodeId(null);
    setHighlightPathsState(new Set());
    setPendingChatPrompt(null);
  }, []);

  const loadGraphPage = useCallback(async (offset) => {
    const session = openedRepo.current;
    if (!session) return;
    session.graphRequest?.abort();
    const request = new AbortController();
    session.graphRequest = request;
    session.graphOffset = offset ?? session.graphOffset ?? 0;
    setGraphLoading(true);
    setGraphError(null);
    try {
      const { data } = await api.get(`/repos/${session.id}/graph`, {
        params: { limit: 120, offset: session.graphOffset }, signal: request.signal, timeout: 20000,
      });
      if (!request.signal.aborted) setGraph(data);
    } catch {
      if (!request.signal.aborted) setGraphError("The knowledge graph couldn’t load. You can still browse your source files.");
    } finally {
      if (!request.signal.aborted) setGraphLoading(false);
    }
  }, []);

  const loadFiles = useCallback(async () => {
    const session = openedRepo.current;
    if (!session) return;
    session.filesRequest?.abort();
    const request = new AbortController();
    session.filesRequest = request;
    setFilesLoading(true);
    setFilesError(null);
    try {
      const all = [];
      const limit = 1000;
      for (let offset = 0; ; offset += limit) {
        const { data } = await api.get(`/repos/${session.id}/files`, {
          params: { limit, offset }, signal: request.signal, timeout: 20000,
        });
        if (request.signal.aborted) return;
        all.push(...data);
        if (data.length < limit) break;
      }
      setFiles(all);
    } catch {
      if (!request.signal.aborted) setFilesError("Couldn’t load the file list. Try again.");
    } finally {
      if (!request.signal.aborted) setFilesLoading(false);
    }
  }, []);

  const startPanels = useCallback((session, data) => {
    if (!hasParsedWorkspace(data) || session.partsStarted) return;
    session.partsStarted = true;
    loadGraphPage(0);
    loadFiles();
  }, [loadGraphPage, loadFiles]);

  const cancelRequests = useCallback(() => {
    const session = openedRepo.current;
    session?.request.abort();
    session?.graphRequest?.abort();
    session?.filesRequest?.abort();
    openedRepo.current = null;
  }, []);

  const loadRepo = useCallback(async (id) => {
    cancelRequests();
    const session = { id, request: new AbortController(), partsStarted: false, polling: false };
    openedRepo.current = session;
    setRepo(null);
    setGraph({ nodes: [], edges: [] });
    setGraphLoading(false);
    setGraphError(null);
    setFiles([]);
    setFilesLoading(false);
    setFilesError(null);
    setCurrentRepoId(id);
    setRepoLoading(true);
    setRepoLoadError(null);
    resetSelection();
    try {
      const { data } = await api.get(`/repos/${id}`, { signal: session.request.signal });
      if (openedRepo.current !== session) return;
      setRepo(data);
      if (data.status !== "ready") setActiveTab("graph");
      // A repository opens as soon as its own record arrives. Panel requests
      // are independent, so a graph outage cannot block files or history.
      startPanels(session, data);
    } catch (e) {
      if (openedRepo.current === session) setRepoLoadError(e?.response?.data?.detail || "Failed to load repository");
    } finally {
      if (openedRepo.current === session) setRepoLoading(false);
    }
  }, [cancelRequests, startPanels, resetSelection]);

  const clearCurrentRepo = useCallback(() => {
    cancelRequests();
    setCurrentRepoId(null);
    setRepo(null);
    setGraph({ nodes: [], edges: [] });
    setFiles([]);
  }, [cancelRequests]);

  const pollRepoStatus = useCallback(async (id) => {
    const session = openedRepo.current;
    if (session?.id !== id || session.polling) return;
    session.polling = true;
    try {
      const { data } = await api.get(`/repos/${id}/status`, { signal: session.request.signal, timeout: 15000 });
      if (openedRepo.current !== session) return;
      setRepo((prev) => prev?.id === id ? { ...prev, ...data } : prev);
      startPanels(session, data);
    } catch (e) {
      if (e.response?.status === 404 && openedRepo.current === session) setRepoLoadError("Repository was deleted.");
    } finally {
      session.polling = false;
    }
  }, [startPanels]);

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

  // ---- shared selection actions -------------------------------------------------------

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
      // repositories list
      repositories,
      reposLoading,
      reposError,
      loadRepositories,
      refreshRepositories,
      addGithubRepo,
      uploadZipRepo,
      deleteRepo,
      reingestRepo,
      // current repo detail
      currentRepoId,
      repo,
      graph,
      graphLoading,
      graphError,
      loadGraphPage,
      files,
      filesLoading,
      filesError,
      loadFiles,
      repoLoading,
      repoLoadError,
      loadRepo,
      clearCurrentRepo,
      pollRepoStatus,
      // selection
      repoId: currentRepoId,
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
      repositories,
      reposLoading,
      reposError,
      loadRepositories,
      refreshRepositories,
      addGithubRepo,
      uploadZipRepo,
      deleteRepo,
      reingestRepo,
      currentRepoId,
      repo,
      graph,
      graphLoading,
      graphError,
      loadGraphPage,
      files,
      filesLoading,
      filesError,
      loadFiles,
      repoLoading,
      repoLoadError,
      loadRepo,
      clearCurrentRepo,
      pollRepoStatus,
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
