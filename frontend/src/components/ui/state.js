import { AlertTriangle, RefreshCw } from "lucide-react";

/** Consistent "nothing here yet" block. `action` is an optional
 * { label, onClick } for a primary call to action. */
export function EmptyState({ icon: Icon, title, subtitle, action, testId }) {
  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-10 text-center" data-testid={testId} role="status">
      {Icon && <Icon size={22} className="mx-auto text-white/25 mb-3" aria-hidden="true" />}
      <div className="text-sm text-white/60">{title}</div>
      {subtitle && <div className="text-xs text-white/35 mt-1.5 max-w-sm mx-auto">{subtitle}</div>}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 text-xs mono border border-[#3FC8E8]/40 text-[#3FC8E8] hover:bg-[#3FC8E8]/10 px-3 py-1.5 rounded-sm transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

/** Consistent error block with a working Retry action. Every API-backed
 * panel should reach for this instead of a bespoke error paragraph. */
export function ErrorState({ message, onRetry, testId, compact = false }) {
  return (
    <div
      className={`bg-[#121212] border border-[#FF3B30]/25 rounded-sm text-center ${compact ? "p-5" : "p-10"}`}
      data-testid={testId}
      role="alert"
      aria-live="polite"
    >
      <AlertTriangle size={compact ? 16 : 20} className="mx-auto text-[#FF3B30] mb-2" aria-hidden="true" />
      <p className="text-sm text-white/70">{message || "Something went wrong."}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 text-xs mono border border-white/15 hover:bg-white/10 px-3 py-1.5 rounded-sm text-white/70 flex items-center gap-1.5 mx-auto transition-colors"
        >
          <RefreshCw size={11} aria-hidden="true" /> Retry
        </button>
      )}
    </div>
  );
}

/** Inline (non-card) variant for use inside toolbars / small slots where a
 * full bordered card would be too heavy. */
export function InlineError({ message, onRetry }) {
  return (
    <div className="flex items-center gap-2 text-xs text-[#FF3B30]" role="alert">
      <AlertTriangle size={12} aria-hidden="true" />
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="underline decoration-dotted hover:text-white">Retry</button>
      )}
    </div>
  );
}
