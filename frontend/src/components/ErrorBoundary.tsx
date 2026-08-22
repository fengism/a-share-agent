import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <section className="app-error-boundary" role="alert">
          <div className="app-error-boundary__icon" aria-hidden="true">!</div>
          <h1>页面加载失败</h1>
          <p>{this.state.error?.message || "发生了未知错误"}</p>
          <button type="button" onClick={this.handleReset}>重试</button>
        </section>
      );
    }
    return this.props.children;
  }
}
