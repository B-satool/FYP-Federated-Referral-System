import { Link as RouterLink } from "react-router-dom";
import { Button, Paper, Stack, Typography } from "@mui/material";
import { usePageTitle } from "../../hooks";

export function NotFound() {
  usePageTitle("Page not found");
  return (
    <Paper sx={{ p: 4, maxWidth: 560 }}>
      <Stack spacing={2}>
        <Typography variant="h5" component="h1">
          Page not found
        </Typography>
        <Typography color="text.secondary">The address may be mistyped, or the page may have moved. Use the start page to continue.</Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" component={RouterLink} to="/">
            Go to start page
          </Button>
        </Stack>
      </Stack>
    </Paper>
  );
}
