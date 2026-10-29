# Device keys are created and unlocked automatically (no passphrase)

**Date:** 2026-10-30. **Decided by:** the project owner ("it shouldn't ask the doctor to set up any device key").
**Status:** decided; it changes spec v4 5.3 ("unlocked with the doctor's passphrase/biometric on that device").

## Decision

A doctor or patient sees records as soon as they are signed in. The browser creates their key pairs on first sign-in,
as non-extractable WebCrypto keys stored in IndexedDB, registers the public halves, and loads them on every later
visit with no prompt. The passphrase, backup file and restore screens were removed.

## What stays the same

End-to-end encryption is unchanged: the private keys are created in the browser and never leave it, and the platform
still holds no private key and no data key (AGENTS.md invariant 13). The server does not open records because someone
is signed in: that option was rejected because it would undo the encryption the team approved.

## Trade-offs (stated in docs/security-model.md)

- **Protection on the device is now the device itself.** Before, the stored key was sealed with a passphrase. Now
  anyone who can use that browser profile *and* sign in as that doctor can read what the doctor can. Signing in is
  still required: the platform sends ciphertext only to the signed-in doctor. Use only personal, locked devices.
- **One device at a time.** Signing in on another browser creates a new key, and the hospital revokes the earlier one
  (its administrators are told). Records from institutions can be requested again. Items that existed only on the
  platform (the doctor's notes, the medicine list, papers) stay readable only with the old key, or from the patient's
  copy.
- **No backup:** a non-extractable key cannot be exported.

## Possible later improvement

Unlock with Windows Hello, a fingerprint or the phone's screen lock (WebAuthn), which ties the key to the device's
hardware without a typed passphrase. Several keys per doctor (one per device) would remove the one-device limit.
