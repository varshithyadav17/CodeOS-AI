export const hasParsedWorkspace = (repo) => repo?.status === "ready"
  || (["embedding", "waiting_embeddings"].includes(repo?.status) && repo?.stats?.nodes > 0);

export const repositoryStatusLabel = (status) => ({
  waiting_embeddings: "AI indexing paused",
  waiting_graph: "Waiting for graph",
  embedding: "AI indexing",
  cloning: "Loading source",
}[status] || status);
