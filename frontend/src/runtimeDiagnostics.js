const enabled =
  import.meta.env.DEV || new URLSearchParams(window.location.search).get("desktop-test") === "1";

if (enabled && !window.__PANELOOM_RUNTIME_DIAGNOSTICS__) {
  const entries = [];

  function clean(value, limit = 2000) {
    return String(value || "")
      .replace(/(api[_-]?key|authorization|bearer)\s*[:=]?\s*[^\s,;]+/gi, "$1=[redacted]")
      .slice(0, limit);
  }

  function record(kind, message, details = {}) {
    entries.push({
      timestamp: new Date().toISOString(),
      kind,
      message: clean(message),
      stack: clean(details.stack || "", 6000),
      source: clean(details.source || "", 1000),
      line: Number(details.line || 0),
      column: Number(details.column || 0),
      route: window.location.hash || "#dashboard",
    });
    if (entries.length > 100) entries.splice(0, entries.length - 100);
  }

  window.__PANELOOM_RUNTIME_DIAGNOSTICS__ = {
    entries,
    record,
    snapshot: () => entries.map((entry) => ({ ...entry })),
  };

  const originalConsoleError = console.error.bind(console);
  console.error = (...args) => {
    record(
      "console.error",
      args.map((item) => (item instanceof Error ? item.message : String(item))).join(" "),
      { stack: args.find((item) => item instanceof Error)?.stack || "" },
    );
    originalConsoleError(...args);
  };

  window.addEventListener("error", (event) => {
    record("window.error", event.message, {
      stack: event.error?.stack,
      source: event.filename,
      line: event.lineno,
      column: event.colno,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    record("unhandledrejection", reason?.message || reason, { stack: reason?.stack });
  });
}
