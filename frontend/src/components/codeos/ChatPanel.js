import { memo, useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { Send, Loader2, FileCode2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useWorkspace } from "../../context/WorkspaceContext";
import { SkeletonList } from "../ui/skeleton";
import { InlineError } from "../ui/state";

const SUGGESTIONS = [
  "Explain the architecture of this repo",
  "What does the entry point do?",
  "Find potential circular dependencies",
  "How does authentication flow work?",
  "Summarize the main modules",
];

const MessageBubble = memo(function MessageBubble({ role, content, contextNodes, onContextClick, failed }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-1 duration-200`}>
      <div className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm ${isUser ? "bg-[#3FC8E8] text-black" : failed ? "bg-[#FF3B30]/10 border border-[#FF3B30]/30 text-white/90" : "glass-panel border border-white/10 text-white/90"}`}>
        <div className="whitespace-pre-wrap leading-relaxed break-words">{content}</div>
        {contextNodes && contextNodes.length > 0 && !isUser && (
          <div className="mt-3 pt-2 border-t border-white/10">
            <div className="text-[9px] mono uppercase tracking-[0.18em] text-white/40 mb-1">Context · click to select</div>
            <div className="flex flex-wrap gap-1">
              {contextNodes.slice(0, 8).map((n, i) => (
                <button
                  key={i}
                  data-testid={`chat-context-chip-${i}`}
                  onClick={() => onContextClick(n)}
                  className="text-[10px] mono text-white/60 hover:text-[#3FC8E8] bg-white/5 hover:bg-white/10 px-1.5 py-0.5 rounded-sm transition-colors duration-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8]"
                  title={n.file_path}
                >
                  {n.name || n.qualified_name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

export default function ChatPanel({ repoId, repoReady }) {
  const { selectedFilePath, selectedNodeId, nodeById, selectNode, pendingChatPrompt, clearPendingChatPrompt } = useWorkspace();
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [convLoading, setConvLoading] = useState(true);
  const [convError, setConvError] = useState(null);
  const [switching, setSwitching] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const loadConversations = useCallback((signal) => {
    setConvLoading(true);
    setConvError(null);
    api.get(`/repos/${repoId}/conversations`, { signal })
      .then((r) => setConversations(r.data))
      .catch((e) => { if (!signal?.aborted && e.code !== "ERR_CANCELED") setConvError(e?.response?.data?.detail || "Failed to load conversations."); })
      .finally(() => { if (!signal?.aborted) setConvLoading(false); });
  }, [repoId]);

  useEffect(() => {
    const controller = new AbortController();
    loadConversations(controller.signal);
    return () => controller.abort();
  }, [loadConversations]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // A quick action elsewhere in the workspace (Files/Graph/Architecture/
  // Timeline/Reviews/Docs "Ask about this…" buttons) calls askInChat(),
  // which stashes a prompt here. We prefill + focus rather than
  // auto-sending, so an LLM call is never fired without the user's OK —
  // and the current conversation/messages are left completely untouched.
  useEffect(() => {
    if (!pendingChatPrompt) return;
    setInput(pendingChatPrompt.text);
    inputRef.current?.focus();
    clearPendingChatPrompt();
  }, [pendingChatPrompt, clearPendingChatPrompt]);

  const loadConversation = async (cid) => {
    if (cid === conversationId) return;
    setSwitching(true);
    try {
      const r = await api.get(`/conversations/${cid}`);
      setConversationId(cid);
      setMessages(r.data.messages.map((m) => ({ role: m.role, content: m.content, contextNodes: [] })));
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to open conversation");
    } finally {
      setSwitching(false);
    }
  };

  const newChat = () => { setConversationId(null); setMessages([]); };

  // The backend's chat endpoint only accepts { message, conversation_id } —
  // there's no separate "context" field, and we're not adding one (no new
  // APIs). So the shared workspace selection (file / graph node) is folded
  // into the *text* of the outgoing message as a short preamble, which the
  // existing retrieval pipeline can use just like any other part of the
  // question. The chat bubble still shows the user's original, unmodified
  // text — only the wire request carries the extra context.
  const buildOutgoing = (message) => {
    const parts = [];
    if (selectedFilePath) parts.push(`selected file: ${selectedFilePath}`);
    if (selectedNodeId) {
      const node = nodeById.get(selectedNodeId);
      if (node) parts.push(`selected symbol: ${node.qualified_name || node.name} (${node.type})`);
    }
    if (parts.length === 0) return message;
    return `[Workspace context — ${parts.join("; ")}]\n\n${message}`;
  };

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    const outgoing = buildOutgoing(message);
    // Optimistic: the user's message renders immediately, before the
    // network round trip completes.
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setSending(true);
    try {
      const r = await api.post(`/repos/${repoId}/chat`, { message: outgoing, conversation_id: conversationId });
      setConversationId(r.data.conversation_id);
      setMessages((m) => [...m, { role: "assistant", content: r.data.message.content, contextNodes: r.data.context }]);
      loadConversations(); // refresh sidebar with new/updated title
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message;
      toast.error(detail || "Chat error");
      setMessages((m) => [...m, { role: "assistant", content: `Couldn't get a response: ${detail}`, failed: true }]);
    } finally { setSending(false); }
  };

  const onContextClick = useCallback((n) => selectNode(n.id), [selectNode]);
  const contextLabel = selectedNodeId ? (nodeById.get(selectedNodeId)?.qualified_name || nodeById.get(selectedNodeId)?.name) : selectedFilePath;

  return (
    <div className="grid grid-cols-12 gap-4 h-[640px]" data-testid="chat-panel">
      {/* Conversations sidebar */}
      <div className="col-span-3 glass-panel border border-white/10 rounded-xl flex flex-col">
        <div className="px-3 py-3 border-b border-white/10 flex items-center justify-between">
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-white/50">Conversations</span>
          <button data-testid="chat-new" onClick={newChat} aria-label="Start a new conversation" className="text-[10px] mono text-[#3FC8E8] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm">+ NEW</button>
        </div>
        <div className="flex-1 overflow-auto" role="list" aria-label="Conversation history">
          {convError ? (
            <div className="p-3"><InlineError message={convError} onRetry={() => loadConversations()} /></div>
          ) : convLoading ? (
            <SkeletonList rows={4} rowClassName="h-8" />
          ) : conversations.length === 0 ? (
            <div className="p-3 text-xs text-white/40">No conversations yet — ask something below to start one.</div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                data-testid={`chat-conv-${c.id}`}
                onClick={() => loadConversation(c.id)}
                aria-current={conversationId === c.id}
                className={`w-full text-left px-3 py-2 text-xs hover:bg-white/5 border-l-2 transition-colors duration-150 ${conversationId === c.id ? "border-[#3FC8E8] bg-white/5" : "border-transparent"} text-white/80 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-[-1px]`}
              >
                <div className="truncate">{c.title}</div>
                <div className="text-[10px] mono text-white/30 mt-0.5">{new Date(c.updated_at).toLocaleString()}</div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="col-span-9 glass-panel border border-white/10 rounded-xl flex flex-col">
        <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
          <Sparkles size={14} className="text-[#3FC8E8]" aria-hidden="true" />
          <span className="text-sm font-medium" style={{ fontFamily: "Chivo" }}>Ask CodeOS AI</span>
          <span className="text-[10px] mono text-white/30 ml-auto">gemini-2.5-pro</span>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-auto p-4 space-y-3" data-testid="chat-messages" aria-live="polite" aria-busy={sending || switching}>
          {switching && (
            <div className="flex items-center justify-center h-full text-white/40 text-sm gap-2" role="status">
              <Loader2 size={14} className="animate-spin" aria-hidden="true" /> Opening conversation…
            </div>
          )}
          {!switching && messages.length === 0 && (
            <div className="text-center text-white/40 text-sm pt-10">
              <FileCode2 size={28} className="mx-auto text-white/30 mb-3" aria-hidden="true" />
              <div className="mb-4">{repoReady ? "Ask anything about this codebase" : "Repo is still indexing — chat available once ready"}</div>
              <div className="flex flex-wrap gap-2 justify-center max-w-md mx-auto">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    data-testid={`chat-suggest-${s.slice(0, 15)}`}
                    disabled={!repoReady}
                    onClick={() => send(s)}
                    className="text-xs border border-white/10 hover:border-[#3FC8E8] hover:text-[#3FC8E8] px-2.5 py-1.5 rounded-sm transition-colors duration-150 text-white/60 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {!switching && messages.map((m, i) => (
            <MessageBubble key={i} role={m.role} content={m.content} contextNodes={m.contextNodes} failed={m.failed} onContextClick={onContextClick} />
          ))}
          {sending && (
            <div className="flex justify-start" role="status">
              <div className="glass-panel border border-white/10 rounded-xl px-3 py-2 text-white/50 text-sm flex items-center gap-2">
                <Loader2 size={14} className="animate-spin text-[#3FC8E8]" aria-hidden="true" /> Thinking…
              </div>
            </div>
          )}
        </div>

        {contextLabel && (
          <div className="px-3 pt-2 flex items-center gap-1.5 animate-in fade-in duration-150" data-testid="chat-context-indicator">
            <span className="text-[10px] mono text-white/40">Including in context:</span>
            <span className="text-[10px] mono text-[#3FC8E8] bg-[#3FC8E8]/10 border border-[#3FC8E8]/25 px-1.5 py-0.5 rounded-sm truncate max-w-[220px]">{contextLabel}</span>
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="border-t border-white/10 p-3 flex gap-2"
          data-testid="chat-input-form"
        >
          <label htmlFor="chat-input-field" className="sr-only">Ask CodeOS AI a question</label>
          <input
            id="chat-input-field"
            ref={inputRef}
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={repoReady ? "Ask about classes, files, dependencies…" : "Waiting for ingestion to finish"}
            disabled={!repoReady || sending}
            className="flex-1 glass-panel-soft border border-white/10 focus-visible:border-[#3FC8E8] focus-visible:ring-1 focus-visible:ring-[#3FC8E8] rounded-xl px-3 py-2 text-sm mono outline-none disabled:opacity-60"
          />
          <button
            data-testid="chat-send-button"
            type="submit"
            disabled={!repoReady || sending || !input.trim()}
            aria-label="Send message"
            className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 disabled:hover:brightness-100 text-black rounded-lg px-4 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px flex items-center gap-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#3FC8E8]"
          >
            <Send size={14} aria-hidden="true" /> Send
          </button>
        </form>
      </div>
    </div>
  );
}
