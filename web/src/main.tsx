import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { AuthProvider } from "./auth/AuthProvider";
import { ApiError } from "./api/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { NotifyProvider, notifyOutsideReact } from "./components/Notify";
import { theme } from "./theme";
import { DeviceKeysProvider } from "./crypto/session";
import App from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  // Every completed action confirms itself. A mutation can set meta.success for a specific
  // message, or meta.silent to skip the confirmation. Failures stay inline next to the form.
  mutationCache: new MutationCache({
    onSuccess: (_data, _vars, _ctx, mutation) => {
      if (mutation.meta?.silent) return;
      notifyOutsideReact(String(mutation.meta?.success ?? "Action completed."));
    },
  }),
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <NotifyProvider>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
              <AuthProvider>
                <DeviceKeysProvider>
                  <App />
                </DeviceKeysProvider>
              </AuthProvider>
            </BrowserRouter>
          </QueryClientProvider>
        </NotifyProvider>
      </ErrorBoundary>
    </ThemeProvider>
  </React.StrictMode>,
);
