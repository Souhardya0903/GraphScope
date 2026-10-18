import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: '2rem',
            margin: '1rem',
            background: 'var(--bg-glass-heavy, #161b22)',
            border: '1px solid var(--accent-rose, #f85149)',
            borderRadius: 12,
            color: 'var(--text-primary, #f0f6fc)',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertCircle size={32} color="var(--accent-rose, #f85149)" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>
            {this.props.fallbackTitle || 'Component Render Error'}
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #8b949e)', maxWidth: 500 }}>
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            onClick={this.handleReset}
            className="apple-btn btn-secondary"
            style={{
              padding: '0.4rem 0.8rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              cursor: 'pointer',
              background: 'rgba(255,255,255,0.08)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: 8,
            }}
          >
            <RefreshCw size={13} />
            <span>Try Again</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
