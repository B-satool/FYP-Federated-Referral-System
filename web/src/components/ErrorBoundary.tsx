import { Component, ReactNode } from "react";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";

/** Catches rendering errors so a fault in one screen shows a recovery page instead of a blank window. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("render error", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2 }}>
        <Paper role="alert" sx={{ p: 4, maxWidth: 520 }}>
          <Stack spacing={2}>
            <Typography variant="h5" component="h1">
              Something went wrong
            </Typography>
            <Typography color="text.secondary">
              This screen could not be displayed. Your saved work is not affected. Reload the page to try again. If the problem continues, tell your institution administrator.
            </Typography>
            <Stack direction="row" spacing={1}>
              <Button variant="contained" onClick={() => window.location.reload()}>
                Reload page
              </Button>
              <Button href="/">Go to start page</Button>
            </Stack>
          </Stack>
        </Paper>
      </Box>
    );
  }
}
