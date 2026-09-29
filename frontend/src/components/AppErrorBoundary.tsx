import { Component, type ErrorInfo, type ReactNode } from "react";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Erro inesperado ao renderizar a aplicação", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="min-h-screen bg-bg p-6 text-text-primary">
        <section
          aria-live="assertive"
          className="mx-auto mt-16 max-w-lg rounded-lg border border-state-error/40 bg-surface p-6 shadow-lg"
        >
          <p className="text-sm font-medium text-state-error">Não foi possível exibir esta tela</p>
          <p className="mt-2 text-sm text-text-secondary">
            Seus dados continuam salvos. Recarregue a página para tentar novamente.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 h-10 rounded bg-state-info px-4 text-sm font-medium text-white"
          >
            Recarregar página
          </button>
        </section>
      </main>
    );
  }
}
