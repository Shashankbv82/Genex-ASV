import React from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#070B12] text-slate-100 flex items-center justify-center p-6 font-sans">
          <div className="max-w-xl w-full bg-[#0E1524] border border-rose-500/40 rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center gap-3 pb-4 border-b border-slate-800">
              <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center flex-shrink-0">
                <AlertOctagon className="w-6 h-6 text-rose-400" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white tracking-wide uppercase">
                  GENEX ASV — Runtime Exception Caught
                </h2>
                <span className="text-xs text-slate-400 font-mono">
                  Component render error intercepted by dashboard ErrorBoundary
                </span>
              </div>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 font-mono text-rose-300 overflow-x-auto">
                {this.state.error?.toString() || 'Unknown error occurred'}
              </div>

              {this.state.errorInfo?.componentStack && (
                <details className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/80 text-[11px] text-slate-400 font-mono">
                  <summary className="cursor-pointer text-slate-300 font-semibold mb-1">
                    Component Stack Trace
                  </summary>
                  <pre className="overflow-x-auto whitespace-pre-wrap">
                    {this.state.errorInfo.componentStack}
                  </pre>
                </details>
              )}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
              >
                Attempt Recovery
              </button>
              <button
                onClick={this.handleReload}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-500 text-slate-950 hover:bg-cyan-400 flex items-center gap-1.5 transition-colors shadow-lg shadow-cyan-500/20"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reload Dashboard</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
