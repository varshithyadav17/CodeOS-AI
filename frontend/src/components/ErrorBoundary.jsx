import { Component } from "react";

/**
 * Catches render/lifecycle errors in its subtree so a bug in one panel
 * (e.g. a single feature panel on the Repo Detail page) can't take down
 * the entire app to a blank white screen.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", error, info?.componentStack);
  }

  handleReset = () => {
    this.setState({ error: null });
    if (this.props.onReset) this.props.onReset();
  };

  render() {
    if (!this.state.error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback({ error: this.state.error, reset: this.handleReset });
    }

    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-white/10 bg-white/5 p-8 text-center">
        <p className="text-sm font-medium text-white/80">
          {this.props.label ? `${this.props.label} hit an error.` : "Something went wrong."}
        </p>
        <p className="max-w-md text-xs text-white/40">
          {this.state.error?.message || "An unexpected error occurred while rendering this section."}
        </p>
        <button
          onClick={this.handleReset}
          className="mt-1 rounded-md border border-white/15 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;
