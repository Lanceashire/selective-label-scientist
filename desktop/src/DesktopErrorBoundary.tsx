import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class DesktopErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ECOMIC desktop render error", error, info.componentStack);
  }

  retry = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return <main className="desktop-fallback" role="alert">
      <section className="desktop-fallback-card">
        <p className="kicker">RECOVERABLE UI ERROR</p>
        <h1>\u9875\u9762\u6e32\u67d3\u51fa\u73b0\u95ee\u9898</h1>
        <p>\u5df2\u4fdd\u7559\u672c\u5730\u7814\u7a76\u6570\u636e\u3002\u8bf7\u91cd\u8bd5\u6216\u8fd4\u56de\u9996\u9875\uff0c\u4e0d\u4f1a\u518d\u663e\u793a\u7a7a\u767d\u9875\u3002</p>
        <pre>{this.state.error.message || "Unknown rendering error"}</pre>
        <div className="actions"><button className="primary" onClick={this.retry}>\u91cd\u8bd5\u6e32\u67d3</button><button onClick={() => window.location.reload()}>\u8fd4\u56de\u9996\u9875</button></div>
      </section>
    </main>;
  }
}