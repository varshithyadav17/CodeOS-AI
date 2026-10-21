import { api } from "./api";

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

// Share in-flight preparation across StrictMode mounts. Later login visits get
// a fresh nonce and install the callback for the current component.
export function prepareGoogleSignIn() {
  if (!preparation) {
    preparation = api.get("/auth/google/challenge", { timeout: 15000 }).then(async ({ data }) => {
      if (!data.enabled) return data;
      return { ...data, identity: await loadLibrary() };
    }).finally(() => { preparation = null; });
  }
  return preparation;
}
