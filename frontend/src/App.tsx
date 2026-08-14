import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./routes";
import { CompanyProvider } from "./contexts/CompanyContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
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
