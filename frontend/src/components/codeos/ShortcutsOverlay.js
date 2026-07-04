import { useEffect, useRef } from "react";
import { X } from "lucide-react";

const TAB_SHORTCUTS = [
  ["1", "AI Chat"], ["2", "Code Review"], ["3", "Architecture"], ["4", "Timeline"],
  ["5", "Docs"], ["6", "Knowledge Graph"], ["7", "Files"],
];

const OTHER_SHORTCUTS = [
  ["Esc", "Clear selection / close dialogs"],
  ["?", "Show this shortcuts overlay"],
];

export default function ShortcutsOverlay({ onClose }) {
  const closeRef = useRef(null);

  // Focus the close button on open so keyboard users land somewhere
  // sensible, and let Escape close it (in addition to the global handler).
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/70 z-[100] flex items-center justify-center p-4 animate-in fade-in duration-150"
      onClick={onClose}
      data-testid="shortcuts-overlay"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        className="w-full max-w-sm glass-panel-soft border border-white/10 rounded-xl p-5 animate-in fade-in zoom-in-95 duration-150"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 id="shortcuts-title" className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Keyboard shortcuts</h2>
          <button ref={closeRef} onClick={onClose} aria-label="Close shortcuts overlay" className="text-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#3FC8E8] rounded-sm">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40 mb-2">Jump to tab</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mb-4">
          {TAB_SHORTCUTS.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 text-xs text-white/70">
              <kbd className="mono text-[10px] bg-white/10 border border-white/10 rounded-sm px-1.5 py-0.5 text-white/80">{key}</kbd>
              {label}
            </div>
          ))}
        </div>
        <div className="text-[10px] mono uppercase tracking-[0.18em] text-white/40 mb-2">Other</div>
        <div className="space-y-1.5">
          {OTHER_SHORTCUTS.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 text-xs text-white/70">
              <kbd className="mono text-[10px] bg-white/10 border border-white/10 rounded-sm px-1.5 py-0.5 text-white/80">{key}</kbd>
              {label}
            </div>
          ))}
        </div>
        <p className="text-[10px] text-white/30 mt-4">Shortcuts are disabled while typing in a text field.</p>
      </div>
    </div>
  );
}
