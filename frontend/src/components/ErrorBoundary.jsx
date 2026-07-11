import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    window.__PANELOOM_RUNTIME_DIAGNOSTICS__?.record?.("react.render", error?.message || error, {
      stack: `${error?.stack || ""}\n${info?.componentStack || ""}`,
    });
  }

  componentDidUpdate(previousProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return this.props.fallback({ error: this.state.error, reset: this.reset });
    }
    return this.props.children;
  }
}

export function PageErrorFallback({ error, onRetry, onDashboard, t }) {
  return (
    <section className="panel error-fallback" role="alert">
      <div>
        <p className="eyebrow">{t("pageErrorEyebrow")}</p>
        <h3>{t("pageErrorTitle")}</h3>
        <p className="muted">{t("pageErrorBody")}</p>
        <details>
          <summary>{t("errorDetails")}</summary>
          <code>{String(error?.message || error || t("unknownError"))}</code>
        </details>
      </div>
      <div className="button-row">
        <button className="primary" onClick={onRetry} type="button">
          {t("retry")}
        </button>
        <button className="secondary" onClick={onDashboard} type="button">
          {t("returnDashboard")}
        </button>
      </div>
    </section>
  );
}

export function GlobalErrorFallback({ error, onRetry }) {
  function returnToDashboard() {
    window.location.hash = "#dashboard";
    window.location.reload();
  }

  return (
    <main className="global-error-fallback" role="alert">
      <section className="panel error-fallback">
        <div>
          <p className="eyebrow">Paneloom</p>
          <h2>界面遇到错误 / The interface encountered an error</h2>
          <p className="muted">可以重试当前界面，或返回总览继续工作。</p>
          <details>
            <summary>错误详情 / Error details</summary>
            <code>{String(error?.message || error || "Unknown error")}</code>
          </details>
        </div>
        <div className="button-row">
          <button className="primary" onClick={onRetry} type="button">重试 / Retry</button>
          <button className="secondary" onClick={returnToDashboard} type="button">
            返回总览 / Dashboard
          </button>
        </div>
      </section>
    </main>
  );
}
