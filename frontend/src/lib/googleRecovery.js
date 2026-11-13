// Only the setup request recovers automatically. Credentials are sent once.
export function googleRetrySeconds(error, fallback = 30, now = Date.now()) {
  const headers = error?.response?.headers;
  const value = headers?.get?.('retry-after') ?? headers?.['retry-after'];
  if (value == null || String(value).trim() === '') return fallback;
  const seconds = Number(value);
  const delay = Number.isFinite(seconds) ? seconds : (Date.parse(value) - now) / 1000;
  return Number.isFinite(delay) ? Math.max(1, Math.ceil(delay)) : fallback;
}

const cancelled = () => Object.assign(new Error('Sign-in setup cancelled.'), { code: 'ERR_CANCELED' });
function waitForRetry(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(cancelled()); return; }
    const abort = () => { clearTimeout(timer); reject(cancelled()); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export async function requestGoogleChallenge(request, {
  wait = waitForRetry, signal, onRetry, now = Date.now,
} = {}) {
  const deadline = now() + 90000;
  for (let attempt = 1; attempt <= 3; attempt++) {
    if (signal?.aborted) throw cancelled();
    try {
      return await request({ signal, timeout: Math.max(1, Math.min(30000, deadline - now())) });
    }
    catch (error) {
      if (signal?.aborted || error?.code === 'ERR_CANCELED') throw error;
      const status = error?.response?.status;
      const transient = [429, 502, 503, 504].includes(status)
        || ['ECONNABORTED', 'ETIMEDOUT', 'ERR_NETWORK'].includes(error?.code);
      const delay = googleRetrySeconds(error, status === 429 ? attempt * 5 : attempt * 2, now());
      if (attempt === 3 || !transient || delay * 1000 + 1000 >= deadline - now()) throw error;
      onRetry?.();
      await wait(delay * 1000, signal);
    }
  }
}

export function googleFailure(error) {
  const status = error?.response?.status;
  if (status === 429) return {
    message: 'The sign-in service is busy. Please wait a moment before trying again.',
    retryAfter: googleRetrySeconds(error),
  };
  if ([502, 503, 504].includes(status) || ['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code)) return {
    message: 'The sign-in service is taking longer to respond. Please try again shortly.', retryAfter: googleRetrySeconds(error, 5),
  };
  if (error?.code === 'ERR_NETWORK') return {
    message: 'Could not reach the sign-in service. Check your connection and try again.', retryAfter: 0,
  };
  const detail = error?.response?.data?.detail;
  return { message: typeof detail === 'string' ? detail : !error?.isAxiosError && error?.message
    ? error.message : 'Google sign-in is unavailable. Please try again.', retryAfter: 0 };
}
