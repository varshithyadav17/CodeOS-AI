import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * Standardizes the "fetch on mount, show loading/error, allow retry, cancel
 * on unmount or path change" pattern that was previously hand-rolled with
 * small inconsistencies (some panels had no .catch, some had no retry, some
 * checked `.error` on the response, some didn't).
 *
 * const { data, loading, error, retry } = useFetch(`/repos/${id}/stats`);
 *
 * - `enabled: false` skips the request entirely (e.g. "wait for repoReady").
 * - `params` is passed straight to axios' `params` and is included in the
 *   effect's dependency (stringified) so changing a query param refetches.
 * - Every request carries an AbortController signal; a request superseded
 *   by a newer one (path/params change, or unmount) is cancelled at the
 *   network layer, not just ignored in state.
 */
export function useFetch(path, { enabled = true, params, transform } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled && !!path, error: null });
  const [nonce, setNonce] = useState(0);
  const paramsKey = params ? JSON.stringify(params) : "";

  const retry = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!enabled || !path) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    api
      .get(path, { params, signal: controller.signal })
      .then((r) => {
        setState({ data: transform ? transform(r.data) : r.data, loading: false, error: null });
      })
      .catch((e) => {
        if (controller.signal.aborted || e.code === "ERR_CANCELED") return;
        setState({ data: null, loading: false, error: e?.response?.data?.detail || e.message || "Request failed" });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, enabled, paramsKey, nonce]);

  return { ...state, retry, setData: (data) => setState((s) => ({ ...s, data })) };
}
