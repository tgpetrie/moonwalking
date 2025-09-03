import React from 'react';

class EnhancedErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // Log to external service in production
    if (process.env.NODE_ENV === 'production') {
      console.error('Error Boundary caught an error:', error, errorInfo);
      // Could integrate with Sentry, LogRocket, etc.
    }
  }

  handleRetry = () => {
    this.setState(prevState => ({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: prevState.retryCount + 1
    }));
  };

  handleReportIssue = () => {
    const errorReport = {
      error: this.state.error?.message,
      stack: this.state.error?.stack,
      componentStack: this.state.errorInfo?.componentStack,
      userAgent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString()
    };

    // Copy error report to clipboard
    navigator.clipboard?.writeText(JSON.stringify(errorReport, null, 2));
    alert('Error report copied to clipboard');
  };

  render() {
    if (this.state.hasError) {
      const { fallback: Fallback, componentName = 'Component' } = this.props;
      
      if (Fallback) {
        return <Fallback 
          error={this.state.error}
          retry={this.handleRetry}
          retryCount={this.state.retryCount}
        />;
      }

      return (
        <div className="bg-red-900/20 border border-red-600 rounded-xl p-6 m-4 text-center">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-lg font-bold text-red-300 mb-2">
            {componentName} Error
          </h2>
          <p className="text-gray-300 text-sm mb-4">
            Something went wrong while rendering this component.
          </p>
          
          <div className="flex justify-center gap-3 mb-4">
            <button
              onClick={this.handleRetry}
              className="px-4 py-2 bg-purple-700 hover:bg-purple-600 text-white rounded text-sm font-semibold"
              disabled={this.state.retryCount >= 3}
            >
              {this.state.retryCount >= 3 ? 'Max Retries Reached' : 'Try Again'}
            </button>
            
            <button
              onClick={this.handleReportIssue}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm"
            >
              Report Issue
            </button>
          </div>

          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details className="mt-4 text-left">
              <summary className="cursor-pointer text-sm text-gray-400 hover:text-white">
                Show Error Details
              </summary>
              <pre className="mt-2 p-3 bg-black/40 rounded text-xs overflow-auto text-red-300">
                {this.state.error.toString()}
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default EnhancedErrorBoundary;