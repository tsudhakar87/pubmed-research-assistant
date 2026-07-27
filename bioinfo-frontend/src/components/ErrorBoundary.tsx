import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode }
interface State { hasError: boolean; message: string }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: '#5c6470' }}>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: 22, marginBottom: 10 }}>Something went wrong</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#9aa1ab' }}>{this.state.message}</div>
          <button
            onClick={() => this.setState({ hasError: false, message: '' })}
            style={{ marginTop: 20, padding: '8px 16px', background: '#1c2430', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
