import { api } from "./api";
import { requestGoogleChallenge } from "./googleRecovery";

let libraryPromise;
let preparation;

function loadLibrary() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (!libraryPromise) {
    libraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      const fail = () => {
        clearTimeout(timer); script.remove(); libraryPromise = null;
        reject(new Error("Google sign-in could not load. Check your connection and try again."));
      };
      const timer = setTimeout(fail, 15000);
      script.onerror = fail;
      script.onload = () => {
        clearTimeout(timer);
        if (window.google?.accounts?.id) resolve(window.google.accounts.id);
        else fail();
      };
      document.head.appendChild(script);
    });
  }
  return libraryPromise;
}

// Share setup across StrictMode mounts, but get a fresh nonce on later visits.
export function prepareGoogleSignIn(onRetry) {
  if (!preparation) {
    const controller = new AbortController();
    const flight = { controller, onRetry, retrying: false, promise: null };
    // Start loading the Google SDK while fetching CodeOS setup. Always handle
    // script errors, including when the challenge itself fails first.
    const identity = loadLibrary().then(value => ({ value }), error => ({ error }));
    flight.promise = requestGoogleChallenge(options => api.get("/auth/google/challenge", options), {
      signal: controller.signal,
      onRetry: () => { flight.retrying = true; flight.onRetry?.(); },
    }).then(async ({ data }) => {
      if (!data.enabled) return data;
      const library = await identity;
      if (library.error) throw library.error;
      if (!data.client_id || !data.nonce) throw new Error("Google sign-in setup could not be loaded.");
      return { ...data, identity: library.value };
    }).finally(() => { if (preparation === flight) preparation = null; });
    preparation = flight;
  } else {
    preparation.onRetry = onRetry;
    if (preparation.retrying) onRetry?.();
  }
  return preparation.promise;
}

export function cancelGoogleSignInSetup() {
  preparation?.controller.abort();
  preparation = null;
}
