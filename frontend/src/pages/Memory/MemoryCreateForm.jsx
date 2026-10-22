import Loader2Icon from "../../assets/icons/loader-2.svg?react";
import XIcon from "../../assets/icons/x.svg?react";
import PlusIcon from "../../assets/icons/plus.svg?react";
import { CATEGORIES } from "./SearchMemory";

/** Modal form for creating a new memory record manually. */
export default function MemoryCreateForm({ repos, draft, setDraft, creating, onSubmit, onClose, firstFieldRef }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 animate-in fade-in duration-150" onClick={onClose} data-testid="memory-create-modal">
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={onSubmit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="memory-create-title"
        className="w-full max-w-md glass-panel-soft border border-white/10 rounded-xl p-5 space-y-3 animate-in fade-in zoom-in-95 duration-150"
      >
        <div className="flex items-center justify-between">
          <h2 id="memory-create-title" className="text-lg tracking-tight font-medium" style={{ fontFamily: "Chivo" }}>New memory</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm"><XIcon width={16} height={16} aria-hidden="true" /></button>
        </div>
        <div>
          <label htmlFor="memory-create-repo" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Repository</label>
          <select ref={firstFieldRef} id="memory-create-repo" data-testid="memory-create-repo" required value={draft.repo_id} onChange={(e) => setDraft({ ...draft, repo_id: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
            <option value="" disabled>Select a repository…</option>
            {repos.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="memory-create-title-input" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Title</label>
          <input id="memory-create-title-input" data-testid="memory-create-title" required value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8]" placeholder="e.g. Revisit retry logic in ingestion pipeline" />
        </div>
        <div>
          <label htmlFor="memory-create-desc" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Description</label>
          <textarea id="memory-create-desc" data-testid="memory-create-description" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} rows={3} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8] resize-none" placeholder="Optional context…" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="memory-create-cat" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Category</label>
            <select id="memory-create-cat" data-testid="memory-create-category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
              {CATEGORIES.filter(Boolean).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="memory-create-sev" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">Severity</label>
            <select id="memory-create-sev" data-testid="memory-create-severity" value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white focus-visible:border-[#3FC8E8]">
              {["critical", "high", "medium", "low", "info"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label htmlFor="memory-create-path" className="text-[10px] mono uppercase tracking-[0.18em] text-white/40">File path (optional)</label>
          <input id="memory-create-path" data-testid="memory-create-filepath" value={draft.file_path} onChange={(e) => setDraft({ ...draft, file_path: e.target.value })} className="w-full mt-1 glass-panel border border-white/10 rounded-xl text-sm px-2 py-1.5 text-white outline-none focus-visible:border-[#3FC8E8] mono" placeholder="src/services/foo.py" />
        </div>
        <button data-testid="memory-create-submit" type="submit" disabled={creating} className="w-full bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 disabled:opacity-50 text-black rounded-lg py-2 text-sm flex items-center justify-center gap-2 mt-2 transition-all duration-200 shadow-[0_4px_14px_-2px_rgba(63,200,232,0.4)] hover:shadow-[0_6px_20px_-2px_rgba(63,200,232,0.55)] hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] focus-visible:outline-offset-2">
          {creating ? <Loader2Icon width={14} height={14} className="animate-spin" aria-hidden="true" /> : <PlusIcon width={14} height={14} aria-hidden="true" />} Add memory
        </button>
      </form>
    </div>
  );
}
