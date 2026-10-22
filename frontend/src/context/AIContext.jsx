import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

const AIContext = createContext(null);

const DEFAULT_CHAT = { conversations: [], convLoading: true, convError: null, conversationId: null, messages: [], sending: false, switching: false };
const DEFAULT_REVIEW = { reviews: [], current: null, loading: true, error: null, running: false, importing: false, imported: false };

function isQuotaError(err) {
  const status = err?.response?.status;
  const detail = String(err?.response?.data?.detail || err?.message || "");
  return status === 429 || detail.includes("RESOURCE_EXHAUSTED") || detail.toLowerCase().includes("quota");
}

const QUOTA_MESSAGE = "AI quota or service capacity is temporarily unavailable. Check your Gemini quota and try again later.";

export function AIProvider({ children }) {
  const [chatState, setChatState] = useState({});
  const [reviewState, setReviewState] = useState({});
  const reviewPollRefs = useRef({});
  useEffect(() => () => { Object.values(reviewPollRefs.current).forEach(clearInterval); }, []);

  const patchChat = useCallback((repoId, patch) => {
    setChatState((s) => ({ ...s, [repoId]: { ...(s[repoId] || {}), ...(typeof patch === "function" ? patch(s[repoId] || {}) : patch) } }));
  }, []);
  const patchReview = useCallback((repoId, patch) => {
    setReviewState((s) => ({ ...s, [repoId]: { ...(s[repoId] || {}), ...(typeof patch === "function" ? patch(s[repoId] || {}) : patch) } }));
  }, []);

  const getChat = useCallback((repoId) => ({ ...DEFAULT_CHAT, ...(chatState[repoId] || {}) }), [chatState]);
  const getReview = useCallback((repoId) => ({ ...DEFAULT_REVIEW, ...(reviewState[repoId] || {}) }), [reviewState]);

  // ---- Chat -----------------------------------------------------------

  const loadConversations = useCallback((repoId, signal) => {
    patchChat(repoId, { convLoading: true, convError: null });
    return api.get(`/repos/${repoId}/conversations`, { signal })
      .then((r) => { patchChat(repoId, { conversations: r.data }); return r.data; })
      .catch((e) => {
        if (!signal?.aborted && e.code !== "ERR_CANCELED") patchChat(repoId, { convError: e?.response?.data?.detail || "Failed to load conversations." });
      })
      .finally(() => { if (!signal?.aborted) patchChat(repoId, { convLoading: false }); });
  }, [patchChat]);

  const loadConversation = useCallback(async (repoId, cid) => {
    const cur = getChat(repoId);
    if (cid === cur.conversationId || cur.sending) return;
    patchChat(repoId, { switching: true });
    try {
      const r = await api.get(`/conversations/${cid}`);
      patchChat(repoId, {
        conversationId: cid,
        messages: r.data.messages.map((m) => ({ role: m.role, content: m.content, contextNodes: [], sources: m.sources || [], relationships: m.relationships || [] })),
      });
    } finally {
      patchChat(repoId, { switching: false });
    }
  }, [getChat, patchChat]);

  const newChat = useCallback((repoId) => {
    if (getChat(repoId).sending) return;
    patchChat(repoId, { conversationId: null, messages: [] });
  }, [getChat, patchChat]);

  const sendChatMessage = useCallback(async (repoId, outgoing, displayText) => {
    const cur = getChat(repoId);
    patchChat(repoId, { messages: [...cur.messages, { role: "user", content: displayText }], sending: true });
    try {
      const r = await api.post(`/repos/${repoId}/chat`, { message: outgoing, conversation_id: cur.conversationId });
      patchChat(repoId, (s) => ({
        conversationId: r.data.conversation_id,
        messages: [...s.messages, { role: "assistant", content: r.data.message.content, contextNodes: r.data.context, sources: r.data.sources || [], relationships: r.data.relationships || [] }],
      }));
      loadConversations(repoId);
      return r.data;
    } catch (err) {
      console.error("[AI Chat error]", err);
      const detail = isQuotaError(err) ? QUOTA_MESSAGE : (err?.response?.data?.detail || err.message);
      patchChat(repoId, (s) => ({
        messages: [...s.messages, { role: "assistant", content: detail, failed: true }],
      }));
      throw err;
    } finally {
      patchChat(repoId, { sending: false });
    }
  }, [getChat, patchChat, loadConversations]);

  // ---- Reviews -----------------------------------------------------------

  const loadReviewList = useCallback(async (repoId) => {
    const r = await api.get(`/repos/${repoId}/reviews`);
    patchReview(repoId, (s) => {
      let current = s.current;
      if (!current) current = r.data.length > 0 ? r.data[0] : null;
      else if (!String(current.id).startsWith("optimistic-")) current = r.data.find((x) => x.id === current.id) || current;
      return { reviews: r.data, error: null, current };
    });
    return r.data;
  }, [patchReview]);

  const loadReviewsInitial = useCallback((repoId) => {
    patchReview(repoId, { loading: true });
    return loadReviewList(repoId)
      .catch((e) => patchReview(repoId, { error: e?.response?.data?.detail || "Failed to load reviews." }))
      .finally(() => patchReview(repoId, { loading: false }));
  }, [loadReviewList, patchReview]);

  const setCurrentReview = useCallback((repoId, review) => {
    patchReview(repoId, { current: review, imported: false });
  }, [patchReview]);

  const stopReviewPoll = useCallback((repoId) => {
    if (reviewPollRefs.current[repoId]) {
      clearInterval(reviewPollRefs.current[repoId]);
      delete reviewPollRefs.current[repoId];
    }
  }, []);

  const pollReview = useCallback((repoId, reviewId) => {
    stopReviewPoll(repoId);
    reviewPollRefs.current[repoId] = setInterval(async () => {
      try {
        const r = await api.get(`/reviews/${reviewId}`);
        patchReview(repoId, { current: r.data });
        if (["done", "failed"].includes(r.data.status)) {
          stopReviewPoll(repoId);
          loadReviewList(repoId).catch(() => {});
        }
      } catch {
        // Transient network hiccups during polling shouldn't interrupt the view.
      }
    }, 2000);
  }, [stopReviewPoll, patchReview, loadReviewList]);

  const startReview = useCallback(async (repoId) => {
    const cur = getReview(repoId);
    patchReview(repoId, { running: true });
    const placeholder = {
      id: `optimistic-${Date.now()}`,
      status: "running",
      progress: 0,
      created_at: new Date().toISOString(),
      summary: "",
      agents: [],
      action_plan: [],
      overall_score: 0,
    };
    const prevCurrent = cur.current;
    patchReview(repoId, (s) => ({ reviews: [placeholder, ...s.reviews], current: placeholder }));
    try {
      const r = await api.post(`/repos/${repoId}/reviews`);
      patchReview(repoId, (s) => ({ reviews: s.reviews.map((x) => (x.id === placeholder.id ? r.data : x)), current: r.data }));
      return r.data;
    } catch (err) {
      console.error("[Review start error]", err);
      patchReview(repoId, (s) => ({ reviews: s.reviews.filter((x) => x.id !== placeholder.id), current: prevCurrent }));
      throw err;
    } finally {
      patchReview(repoId, { running: false });
    }
  }, [getReview, patchReview]);

  const importReviewToMemory = useCallback(async (repoId, reviewId) => {
    patchReview(repoId, { importing: true });
    try {
      const r = await api.post(`/memory/import/${reviewId}`);
      return r.data;
    } finally {
      patchReview(repoId, { importing: false });
    }
  }, [patchReview]);

  const setReviewImported = useCallback((repoId, imported) => {
    patchReview(repoId, { imported });
  }, [patchReview]);

  const value = {
    getChat, loadConversations, loadConversation, newChat, sendChatMessage,
    getReview, loadReviewsInitial, loadReviewList, setCurrentReview, pollReview, stopReviewPoll,
    startReview, importReviewToMemory, setReviewImported,
    isQuotaError, QUOTA_MESSAGE,
  };

  return <AIContext.Provider value={value}>{children}</AIContext.Provider>;
}

export function useAI() {
  const ctx = useContext(AIContext);
  if (!ctx) {
    throw new Error("useAI() must be used within an <AIProvider>");
  }
  return ctx;
}

export { isQuotaError, QUOTA_MESSAGE };
