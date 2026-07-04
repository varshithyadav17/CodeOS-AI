import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { FcGoogle } from "react-icons/fc";
import { Loader2 } from "lucide-react";
import logoLight from "../assets/logo-light.svg";

export default function AuthPage() {
  const nav = useNavigate();
  const { login, signup } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
        toast.success("Welcome back");
      } else {
        await signup(email, password, name);
        toast.success("Account created");
      }
      nav("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  const googleLogin = () => {
    // Standalone build: Google OAuth is wired up to the backend route
    // `/api/auth/google` but requires `GOOGLE_CLIENT_ID` /
    // `GOOGLE_CLIENT_SECRET` to be configured. Show a clear message until
    // the operator provides credentials.
    toast.info(
      "Google sign-in is not configured yet. Use email / password, or set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env."
    );
  };

  return (
    <div className="min-h-screen flex text-white relative">
      <div className="auth-background" aria-hidden="true" />
      {/* Left panel */}
      <div className="hidden md:flex w-1/2 flex-col justify-between p-12 border-r border-white/10 dot-grid relative overflow-hidden z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-[#3FC8E8]/5 pointer-events-none" />
        <div className="relative">
          <div className="flex flex-col gap-2 mb-8">
            <img src={logoLight} alt="CodeOS AI" className="h-8 w-auto" />
            <div className="text-[10px] mono uppercase tracking-[0.2em] text-white/40">The AI Operating System for Software</div>
          </div>
        </div>

        <div className="relative space-y-6 max-w-md">
          <h1 className="text-4xl font-semibold tracking-tighter leading-[1.1]" style={{ fontFamily: "Chivo" }}>
            Repositories,<br />
            <span className="text-[#3FC8E8]">reasoned about</span> by an AI<br />that actually understands code.
          </h1>
          <p className="text-sm text-white/60 leading-relaxed">
            Tree-sitter parsing &rarr; Knowledge Graph &rarr; Hybrid GraphRAG retrieval &rarr; Gemini 2.5 Pro. Ask about architecture, dependencies, security risks, or how a request flows from API to database.
          </p>
          <div className="grid grid-cols-3 gap-3 pt-4">
            {[
              { k: "Parse", v: "Tree-sitter" },
              { k: "Graph", v: "Knowledge KG" },
              { k: "Reason", v: "Gemini 2.5 Pro" },
            ].map((c) => (
              <div key={c.k} className="glass-panel-soft p-3 rounded-lg glass-interactive">
                <div className="text-[10px] uppercase tracking-[0.18em] text-white/40 mono">{c.k}</div>
                <div className="text-xs mt-1 text-white/80">{c.v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative text-[10px] text-white/30 mono uppercase tracking-[0.2em]">
          v0.1.0 · Phase 1
        </div>
      </div>

      {/* Right panel - form */}
      <div className="flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="w-full max-w-sm glass-panel rounded-2xl p-8">
          <div className="mb-8">
            <div className="text-[10px] uppercase tracking-[0.2em] text-white/40 mono mb-2">
              {mode === "login" ? "// authenticate" : "// create account"}
            </div>
            <h2 className="text-3xl tracking-tight font-semibold" style={{ fontFamily: "Chivo" }}>
              {mode === "login" ? "Sign in" : "Create account"}
            </h2>
            <p className="text-sm text-white/50 mt-2">
              {mode === "login" ? "Welcome back to your engineering OS." : "Start indexing your repositories."}
            </p>
          </div>

          <button
            type="button"
            data-testid="google-login-button"
            onClick={googleLogin}
            className="w-full flex items-center justify-center gap-3 border border-white/10 hover:border-white/25 bg-white/[0.03] hover:bg-white/[0.07] text-white py-2.5 rounded-lg text-sm transition-all duration-200 mb-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8]"
          >
            <FcGoogle size={18} aria-hidden="true" /> Continue with Google
          </button>

          <div className="flex items-center gap-3 my-5 text-[10px] uppercase tracking-[0.2em] text-white/30 mono">
            <div className="flex-1 h-px bg-white/10" /> or use email <div className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={submit} className="space-y-3" data-testid="auth-form">
            {mode === "signup" && (
              <div>
                <Label htmlFor="signup-name" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Name</Label>
                <Input id="signup-name" data-testid="signup-name-input" value={name} onChange={(e) => setName(e.target.value)} required className="bg-white/[0.03] border-white/10 rounded-lg focus-visible:border-[#3FC8E8] focus-visible:ring-2 focus-visible:ring-[#3FC8E8]/40 mt-1" />
              </div>
            )}
            <div>
              <Label htmlFor="auth-email" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Email</Label>
              <Input id="auth-email" data-testid="auth-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="bg-white/[0.03] border-white/10 rounded-lg focus-visible:border-[#3FC8E8] focus-visible:ring-2 focus-visible:ring-[#3FC8E8]/40 mt-1" />
            </div>
            <div>
              <Label htmlFor="auth-password" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Password</Label>
              <Input id="auth-password" data-testid="auth-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} className="bg-white/[0.03] border-white/10 rounded-lg focus-visible:border-[#3FC8E8] focus-visible:ring-2 focus-visible:ring-[#3FC8E8]/40 mt-1" />
            </div>
            <Button
              data-testid="auth-submit-button"
              type="submit"
              disabled={busy}
              className="w-full bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black font-medium rounded-lg py-2 mt-2 disabled:opacity-60 shadow-[0_6px_20px_-4px_rgba(63,200,232,0.5)] hover:shadow-[0_8px_26px_-4px_rgba(63,200,232,0.65)] transition-all duration-200"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            data-testid="auth-mode-toggle"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="w-full text-center text-xs text-white/50 hover:text-white mt-6 transition-colors"
          >
            {mode === "login" ? "Need an account? Sign up →" : "Already have an account? Sign in →"}
          </button>
        </div>
      </div>
    </div>
  );
}
