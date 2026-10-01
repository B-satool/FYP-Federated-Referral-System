import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { AuthProvider } from "./auth/AuthProvider";
import { ApiError } from "./api/client";
import App from "./App";
import "./styles.css";

const theme = createTheme({
  palette: { primary: { main: "#1f5c99" }, secondary: { main: "#6a3d9a" } },
  shape: { borderRadius: 6 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiPaper: { defaultProps: { variant: "outlined" } },
  },
});

const queryClient = new QueryClient({
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
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
