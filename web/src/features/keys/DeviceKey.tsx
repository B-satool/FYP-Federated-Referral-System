import { ReactNode, useRef, useState } from "react";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Paper, Stack, TextField, Typography } from "@mui/material";
import KeyIcon from "@mui/icons-material/Key";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import { errorMessage } from "../../api/client";
import { PageHeader, Tag } from "../../components/common";
import { usePageTitle } from "../../hooks";
import { useDeviceKeys } from "../../crypto/session";

const EXPLAIN = "Your login proves who you are; your device key decrypts the data.";

/** Passphrase prompt shared by set-up, unlock, restore and replacement. */
function PassphraseDialog({ open, title, intro, confirm, action, onClose, file }: {
  open: boolean; title: string; intro: ReactNode; confirm: boolean; file?: boolean;
  action: (passphrase: string, fileText?: string) => Promise<void>; onClose: () => void;
}) {
  const [pass, setPass] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [fileText, setFileText] = useState<string | undefined>();
  const input = useRef<HTMLInputElement>(null);
  const mismatch = confirm && again.length > 0 && pass !== again;
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await action(pass, fileText);
      setPass("");
      setAgain("");
      onClose();
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography variant="body2">{intro}</Typography>
          {file && (
            <Box>
              <input ref={input} type="file" accept="application/json" hidden
                onChange={async (e) => setFileText(await e.target.files?.[0]?.text())} />
              <Button variant="outlined" onClick={() => input.current?.click()}>{fileText ? "Backup file chosen" : "Choose backup file"}</Button>
            </Box>
          )}
          <TextField label="Passphrase" type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoFocus
            onKeyDown={(e) => e.key === "Enter" && !confirm && pass && submit()} inputProps={{ "data-testid": "passphrase" }} />
          {confirm && (
            <TextField label="Passphrase again" type="password" value={again} onChange={(e) => setAgain(e.target.value)}
              error={mismatch} helperText={mismatch ? "The passphrases differ" : "At least 10 characters. It cannot be reset: keep it safe."}
              inputProps={{ "data-testid": "passphrase-again" }} />
          )}
          {busy && <Alert severity="info">Working… protecting a key with a passphrase takes a few seconds.</Alert>}
          {err && <Alert severity="error">{err}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !pass || (confirm && pass !== again) || (file && !fileText)}>
          Continue
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Device key status with set-up, unlock, backup, restore and replacement. Shown wherever records are read. */
export function DeviceKeyPanel({ compact = false }: { compact?: boolean }) {
  const dk = useDeviceKeys();
  const [dialog, setDialog] = useState<"setup" | "unlock" | "restore" | "replace" | null>(null);
  if (dk.status === "loading" || dk.kind === null) return null;
  if (dk.status === "unavailable") {
    return <Alert severity="warning">This browser cannot hold encryption keys (it needs WebCrypto and IndexedDB), so records cannot be opened here.</Alert>;
  }
  const who = dk.kind === "patient" ? "your referrals and records" : "patient records";
  const stateTag = dk.status === "unlocked"
    ? dk.keyState === "active" ? <Tag tone="ok" label="Unlocked, signed" />
      : dk.keyState === "pending" ? <Tag tone="wait" label="Unlocked, waiting for your hospital to sign it" />
        : dk.keyState === "revoked" ? <Tag tone="bad" label="Revoked: replace it" /> : <Tag tone="info" label="Unlocked" />
    : dk.status === "locked" ? <Tag tone="warn" label="Locked" /> : <Tag tone="off" label="No key on this device" />;
  return (
    <Paper variant="outlined" sx={{ p: compact ? 1.5 : 2, mb: 2 }} data-testid="device-key">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} justifyContent="space-between">
        <Stack direction="row" spacing={1.5} alignItems="center">
          {dk.status === "unlocked" ? <LockOpenIcon color="success" /> : <KeyIcon color="action" />}
          <Box>
            <Stack direction="row" spacing={1} alignItems="center"><Typography fontWeight={600}>Device key</Typography>{stateTag}</Stack>
            <Typography variant="body2" color="text.secondary">{EXPLAIN}</Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {dk.status === "none" && <Button variant="contained" onClick={() => setDialog("setup")}>Set up device key</Button>}
          {dk.status === "none" && <Button onClick={() => setDialog("restore")}>Restore from backup</Button>}
          {dk.status === "locked" && <Button variant="contained" onClick={() => setDialog("unlock")}>Unlock</Button>}
          {dk.status === "unlocked" && <Button onClick={dk.lock}>Lock</Button>}
          {dk.status !== "none" && !compact && <Button onClick={dk.downloadBackup}>Download backup</Button>}
          {!compact && dk.status !== "none" && <Button color="warning" onClick={() => setDialog("replace")}>I lost my key: replace it</Button>}
        </Stack>
      </Stack>
      <PassphraseDialog open={dialog === "setup"} title="Set up your device key" confirm onClose={() => setDialog(null)}
        intro={<>Your keys are created in this browser. Only the public keys leave it{dk.kind === "doctor" ? ", signed by your hospital" : ""}. The passphrase protects the private keys on this device and is needed to open {who}. {EXPLAIN}</>}
        action={(p) => dk.setup(p)} />
      <PassphraseDialog open={dialog === "unlock"} title="Unlock your device key" confirm={false} onClose={() => setDialog(null)}
        intro={<>Enter your passphrase to open {who} in this tab. The keys stay in this tab's memory until you lock or close it.</>}
        action={(p) => dk.unlock(p)} />
      <PassphraseDialog open={dialog === "restore"} title="Restore from a backup file" confirm={false} file onClose={() => setDialog(null)}
        intro="Choose the backup file you downloaded earlier and enter its passphrase."
        action={(p, text) => dk.restore(text ?? "", p)} />
      <PassphraseDialog open={dialog === "replace"} title="Replace a lost key" confirm onClose={() => setDialog(null)}
        intro={dk.kind === "doctor"
          ? "A new key is created and your hospital revokes the old one; its administrators are told. Records from other institutions are requested again for your open referrals. Items that existed only on the platform (your notes, scans, the medicine list) can be recovered only from the patient's own copy; otherwise they are lost."
          : "A new key is created and the old one is revoked. Copies kept on this device stay readable only with the old key."}
        action={(p) => dk.setup(p, true)} />
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
        Losing the passphrase or this browser's data without a backup means a new key is needed. Download a backup file and keep it somewhere
        safe; it is useless without the passphrase.
      </Alert>
    </>
  );
}

/** Wrap content that needs an unlocked key (doctor or patient screens that decrypt). */
export function NeedsUnlockedKey({ children }: { children: ReactNode }) {
  const dk = useDeviceKeys();
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  return <>{children}</>;
}
