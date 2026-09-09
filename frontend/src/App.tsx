import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./routes";
import { CompanyProvider } from "./contexts/CompanyContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 10 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CompanyProvider><BrowserRouter><AppRoutes /></BrowserRouter></CompanyProvider>
    </QueryClientProvider>
  );
}
