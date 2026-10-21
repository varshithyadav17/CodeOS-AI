import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { prepareGoogleSignIn } from "../../lib/googleIdentity";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import googleIcon from "../../assets/icons/google.svg";

export default function GoogleSignIn({ busy, onSignedIn }) {
  const { googleExchange } = useAuth();
  const buttonRef = useRef(null);
  const handlerRef = useRef(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [credential, setCredential] = useState(null);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false);

  handlerRef.current = async (token, linkPassword) => {
    if (busy || inFlight.current) return;
    if (!token) { setError("Google did not return a credential. Please try again."); return; }
    inFlight.current = true; setSubmitting(true); setError("");
    try {
      await googleExchange(token, linkPassword);
      onSignedIn();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail?.code === "google_link_required") setCredential(token);
      else setError(typeof detail === "string" ? detail : "Google sign-in failed. Please try again.");
    } finally { inFlight.current = false; setSubmitting(false); }
  };

  useEffect(() => {
    let active = true;
    prepareGoogleSignIn().then(({ enabled, identity, client_id, nonce }) => {
      if (!active) return;
      if (!enabled) { setState("disabled"); return; }
      identity.initialize({ client_id, nonce, auto_select: false,
        callback: ({ credential: token }) => { if (active) handlerRef.current(token); } });
      buttonRef.current.replaceChildren();
      identity.renderButton(buttonRef.current, { type: "standard", theme: "outline",
        size: "large", text: "continue_with", shape: "rectangular",
        width: Math.min(340, Math.floor(buttonRef.current.clientWidth)) });
      setState("ready");
    }).catch((err) => {
      if (active) { setState("error"); setError(err.message || "Google sign-in is unavailable."); }
    });
    return () => { active = false; };
  }, [attempt]);

  const refresh = () => {
    setCredential(null); setPassword(""); setError(""); setState("loading");
    setAttempt((value) => value + 1);
  };

  return <div className="mb-4 space-y-3" data-testid="google-signin">
    {(state === "disabled" || state === "error") && <button type="button" disabled
      data-testid="google-unavailable-button" aria-describedby="google-availability"
      className="w-full min-h-10 flex items-center justify-center gap-3 rounded border border-white/20 bg-white/90 text-sm text-gray-600 cursor-not-allowed">
      <img src={googleIcon} alt="" width="18" height="18" /> Continue with Google
    </button>}
    <div ref={buttonRef} data-testid="google-official-button"
      inert={busy || submitting || credential ? "" : undefined}
      className={state === "disabled" || state === "error" ? "hidden" : "min-h-10 flex justify-center w-full"} />
    {state === "loading" && <p role="status" className="text-xs text-white/50 text-center">Loading Google sign-in…</p>}
    {state === "disabled" && <p id="google-availability" className="text-xs text-white/50 text-center">Google sign-in is not available yet. You can sign in with email below.</p>}
    {submitting && <p role="status" className="text-xs text-white/60">Signing in…</p>}
    {credential && <form data-testid="google-link-form" className="space-y-3 rounded-lg border border-white/15 p-3"
      onSubmit={(event) => { event.preventDefault(); handlerRef.current(credential, password); }}>
      <p className="text-xs text-white/70">An account already uses this email. Enter your existing <strong>CodeOS password</strong> to connect Google.</p>
      <label htmlFor="google-link-password" className="text-xs">CodeOS password</label>
      <Input id="google-link-password" type="password" autoComplete="current-password" required maxLength={128}
        value={password} onChange={(event) => setPassword(event.target.value)} />
      <Button type="submit" disabled={busy || submitting}>Connect Google and sign in</Button>
      <button type="button" onClick={refresh} disabled={submitting} className="text-xs text-white/60 ml-2">Cancel</button>
    </form>}
    {error && <p id="google-availability" role="alert" className="text-xs text-red-300">{error}</p>}
    {(error || state === "error") && <button type="button" onClick={refresh} disabled={submitting}
      className="text-xs text-[#3FC8E8] underline">Refresh Google sign-in</button>}
  </div>;
}
