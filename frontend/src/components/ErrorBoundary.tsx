import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode }
interface State { hasError: boolean; error: string }

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: '' };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-slate-400">
          <p className="text-lg font-semibold text-red-400 mb-2">Something went wrong</p>
          <p className="text-xs text-slate-500 mb-4">{this.state.error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-xs bg-slate-800 border border-slate-700 rounded hover:bg-slate-700 transition-colors"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
