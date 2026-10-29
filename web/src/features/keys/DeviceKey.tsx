import { ReactNode, useState } from "react";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import KeyIcon from "@mui/icons-material/Key";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import { PageHeader, Tag } from "../../components/common";
import { usePageTitle } from "../../hooks";
import { useDeviceKeys } from "../../crypto/session";

const EXPLAIN = "Your login proves who you are; this device's key decrypts the data. It was set up automatically and never leaves this browser.";

/**
 * Device key status. Keys are created and loaded automatically on sign-in (crypto/session.tsx); this panel shows up
 * only while that happens, if it failed (with a retry), or on the Device key page.
 */
export function DeviceKeyPanel({ compact = false }: { compact?: boolean }) {
  const dk = useDeviceKeys();
  const [replace, setReplace] = useState(false);
  if (dk.status === "loading" || dk.kind === null) return null;
  if (dk.status === "unavailable") {
    return <Alert severity="warning">This browser cannot hold encryption keys (it needs WebCrypto and IndexedDB), so records cannot be opened here.</Alert>;
  }
  if (dk.status === "preparing") {
    return (
      <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} data-testid="device-key">
        <Typography variant="body2">Preparing this device's key…</Typography>
        <LinearProgress sx={{ mt: 1 }} />
      </Paper>
    );
  }
  const stateTag = dk.status === "unlocked"
    ? dk.keyState === "active" ? <Tag tone="ok" label="Ready, signed" />
      : dk.keyState === "pending" ? <Tag tone="wait" label="Waiting for your hospital to sign it" />
        : dk.keyState === "revoked" ? <Tag tone="bad" label="Revoked" /> : <Tag tone="info" label="Ready" />
    : <Tag tone="bad" label="Not ready" />;
  if (compact && dk.status === "unlocked") return null;
  return (
    <Paper variant="outlined" sx={{ p: compact ? 1.5 : 2, mb: 2 }} data-testid="device-key">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} justifyContent="space-between">
        <Stack direction="row" spacing={1.5} alignItems="center">
          {dk.status === "unlocked" ? <LockOpenIcon color="success" /> : <KeyIcon color="action" />}
          <Box>
            <Stack direction="row" spacing={1} alignItems="center"><Typography fontWeight={600}>Device key</Typography>{stateTag}</Stack>
            <Typography variant="body2" color="text.secondary">{EXPLAIN}</Typography>
            {dk.status === "failed" && <Typography variant="body2" color="error">{dk.error}</Typography>}
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {dk.status === "failed" && <Button variant="contained" onClick={() => void dk.setup(true)}>Try again</Button>}
          {!compact && dk.status === "unlocked" && <Button color="warning" onClick={() => setReplace(true)}>Replace this device's key</Button>}
        </Stack>
      </Stack>
      <Dialog open={replace} onClose={() => setReplace(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Replace this device's key</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            {dk.kind === "doctor"
              ? "A new key is created here and your hospital revokes the old one; its administrators are told. Records from other institutions can be requested again for your open referrals. Items that existed only on the platform (your notes, scans, the medicine list) stay readable only with the old key, or from the patient's own copy."
              : "A new key is created here and the old one is revoked. Copies saved with the old key stay readable only with it."}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReplace(false)}>Cancel</Button>
          <Button variant="contained" color="warning" onClick={() => { setReplace(false); void dk.setup(true); }}>Replace</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

export function KeysPage() {
  usePageTitle("Device key");
  return (
    <>
      <PageHeader title="Device key" subtitle="Records are stored encrypted and decrypted only on the clinician's (or patient's) own device." />
      <DeviceKeyPanel />
      <Alert severity="info">
        Each browser you sign in on gets its own key automatically. Signing in on a new browser or device replaces the
        key used before: records from other institutions can be requested again, but items that existed only on the
        platform stay readable only on the earlier device (or from the patient's own copy).
      </Alert>
    </>
  );
}

/** Wrap content that needs the device key (doctor or patient screens that decrypt). */
export function NeedsUnlockedKey({ children }: { children: ReactNode }) {
  const dk = useDeviceKeys();
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  return <>{children}</>;
}
