import React from "react";

/**
 * Prevents the "confusing blank screen" failure mode the audit flagged:
 * any uncaught render error below this boundary shows a plain recovery
 * screen instead of a white page with no explanation.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("SyncSupply render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-shell">
          <div className="screen" style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
            <h1>Something went wrong</h1>
            <p>Please reload the page. If this keeps happening, try again in a moment.</p>
            <button className="btn btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
