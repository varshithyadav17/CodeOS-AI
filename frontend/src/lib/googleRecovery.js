// Recovery applies to the read-only setup request, never credential exchanges.
export function googleRetrySeconds(error, fallback = 30, now = Date.now()) {
  const headers = error?.response?.headers;
  const value = headers?.get?.('retry-after') ?? headers?.['retry-after'];
  if (value == null || String(value).trim() === '') return fallback;
  const seconds = Number(value);
  const delay = Number.isFinite(seconds) ? seconds : (Date.parse(value) - now) / 1000;
  return Number.isFinite(delay) ? Math.max(1, Math.ceil(delay)) : fallback;
}

export async function requestGoogleChallenge(request, wait = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try { return await request(); }
    catch (error) {
      const status = error?.response?.status;
      const delay = status === 429 ? googleRetrySeconds(error, 5) : 2;
      if (attempt || ![429, 502, 503, 504].includes(status) || delay > 10) throw error;
      await wait(delay * 1000);
    }
  }
}

export function googleFailure(error) {
  const status = error?.response?.status;
  if (status === 429) return {
    message: 'Google sign-in is temporarily rate-limited. Please wait before trying again.',
    retryAfter: googleRetrySeconds(error),
  };
  if ([502, 503, 504].includes(status) || ['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code)) return {
    message: 'The sign-in service is taking longer to respond. Please try again shortly.', retryAfter: 5,
  };
  if (error?.code === 'ERR_NETWORK') return {
    message: 'Could not reach the sign-in service. Check your connection and try again.', retryAfter: 0,
  };
  const detail = error?.response?.data?.detail;
  return { message: typeof detail === 'string' ? detail : !error?.isAxiosError && error?.message
    ? error.message : 'Google sign-in is unavailable. Please try again.', retryAfter: 0 };
}
