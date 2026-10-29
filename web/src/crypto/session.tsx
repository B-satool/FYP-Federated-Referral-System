/**
 * The signed-in user's device keys for this browser session.
 *
 * "Your login proves who you are; your device key decrypts the data." Keycloak sign-in gives a session; reading
 * records needs the private keys kept on this device, sealed with the user's passphrase. Unlocking imports them as
 * non-extractable keys held only in this tab's memory; they are never sent anywhere. Doctors also receive their
 * departments' group keys (wrapped to their own key) when they unlock.
 */
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, Service } from "../api/client";
import { useMe, hasRole } from "../hooks";
import { DirectoryRow, verifiedEntry } from "./directory";
import { backupFile, DeviceKeyRecord, loadDeviceKeys, parseBackup, saveDeviceKeys } from "./keystore";
import {
  DirectoryEntry, exportPkcs8, exportSpki, generateEncryptionKeyPair, generateSigningKeyPair, groupContext,
  importEncPrivate, importSigPrivate, keyId, openWithPassphrase, publicFromPkcs8, sealWithPassphrase, signObject,
  unwrap, Wrapped,
} from "./suite";

export type UnlockedKeys = {
  encPrivate: CryptoKey;
  sigPrivate: CryptoKey;
  encPublic: string;
  sigPublic: string;
  encKeyId: string;
  entry: DirectoryEntry | null; // the issuer-signed directory entry (null while an administrator has not signed it)
  groups: Map<string, CryptoKey>; // "hospital|department|version" -> group private key
};

type Status = "loading" | "unavailable" | "none" | "locked" | "unlocked";

type DeviceKeys = {
  status: Status;
  kind: "doctor" | "patient" | null;
  subjectId: string | null;
  record: DeviceKeyRecord | null;
  keys: UnlockedKeys | null;
  /** server-side state of the key: active (signed), pending (waits for an administrator), revoked, or none */
  keyState: string | null;
  setup: (passphrase: string, recovery?: boolean) => Promise<void>;
  unlock: (passphrase: string) => Promise<void>;
  lock: () => void;
  downloadBackup: () => void;
  restore: (fileText: string, passphrase: string) => Promise<void>;
  groupKey: (hospital: string, department: string, version: number) => CryptoKey | null;
  refresh: () => Promise<void>;
};

const Ctx = createContext<DeviceKeys | null>(null);
const REGISTRATION = "refx.key.registration/v1";
const MIN_PASSPHRASE = 10;

type MyDirectory = {
  subject_id: string;
  entries: DirectoryRow[];
  group_wraps: { hospital_id: string; department: string; group_version: number; member_key_id: string; wrapped: Wrapped }[];
};

export function DeviceKeysProvider({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const kind = hasRole(me, "patient") ? "patient" : hasRole(me, "clinician") ? "doctor" : null;
  const subjectId = me ? (kind === "patient" ? `patient:${me.id}` : me.id) : null;
  const [record, setRecord] = useState<DeviceKeyRecord | null>(null);
  const [keys, setKeys] = useState<UnlockedKeys | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [keyState, setKeyState] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    if (!kind) {
      setStatus("unavailable");
      return;
    }
    if (!globalThis.crypto?.subtle || !("indexedDB" in globalThis)) {
      setStatus("unavailable");
      return;
    }
    loadDeviceKeys(me.id).then((rec) => {
      setRecord(rec ?? null);
      setStatus(rec ? "locked" : "none");
    }, () => setStatus("unavailable"));
  }, [me, kind]);

  const serverState = useCallback(async (encKeyId: string | null): Promise<{ state: string | null; dir: MyDirectory | null }> => {
    const dir = await api.get<MyDirectory>("/e2e/directory/me").catch(() => null);
    const row = dir?.entries.find((r) => r.entry.enc_key_id === encKeyId);
    if (row) return { state: row.revoked ? "revoked" : "active", dir };
    if (kind === "doctor" && me?.institution_id) {
      const mine = await api.get<{ enc_key_id: string; status: string }[]>("/e2e/keys/doctor/me", me.institution_id as Service).catch(() => []);
      return { state: mine.find((k) => k.enc_key_id === encKeyId)?.status ?? null, dir };
    }
    return { state: null, dir };
  }, [kind, me]);

  const loadGroups = useCallback(async (dir: MyDirectory | null, encPrivate: CryptoKey, encKeyId: string) => {
    const groups = new Map<string, CryptoKey>();
    for (const w of dir?.group_wraps ?? []) {
      if (w.member_key_id !== encKeyId) continue;
      try {
        const pkcs8 = await unwrap(encPrivate, w.wrapped, groupContext(w.hospital_id, w.department, w.group_version, encKeyId));
        // the unwrapped key must be the private half of the hospital-signed department entry for that version
        const rows = await api.get<DirectoryRow[]>(`/e2e/directory/departments/${w.hospital_id}/${w.department}`);
        const row = rows.find((r) => r.entry.key_version === w.group_version);
        const entry = row ? await verifiedEntry({ ...row, revocation: null, revoked: false }) : null;
        if (!entry || entry.enc_public_key !== (await publicFromPkcs8(pkcs8))) continue;
        groups.set(`${w.hospital_id}|${w.department}|${w.group_version}`, await importEncPrivate(pkcs8));
      } catch {
        /* a wrap that does not open or does not match is ignored */
      }
    }
    return groups;
  }, []);

  const activate = useCallback(async (rec: DeviceKeyRecord, passphrase: string) => {
    const encPkcs8 = await openWithPassphrase(passphrase, rec.enc_blob);
    const sigPkcs8 = await openWithPassphrase(passphrase, rec.sig_blob);
    const encPrivate = await importEncPrivate(encPkcs8);
    const sigPrivate = await importSigPrivate(sigPkcs8);
    encPkcs8.fill(0);
    sigPkcs8.fill(0);
    const encKeyId = await keyId(rec.enc_public);
    const { state, dir } = await serverState(encKeyId);
    const row = dir?.entries.find((r) => r.entry.enc_key_id === encKeyId && !r.revoked);
    const entry = row ? await verifiedEntry(row).catch(() => null) : null;
    const groups = kind === "doctor" ? await loadGroups(dir, encPrivate, encKeyId) : new Map<string, CryptoKey>();
    setKeys({ encPrivate, sigPrivate, encPublic: rec.enc_public, sigPublic: rec.sig_public, encKeyId, entry, groups });
    setKeyState(state);
    setStatus("unlocked");
  }, [kind, loadGroups, serverState]);

  const register = useCallback(async (encPublic: string, sigPublic: string, sigPrivate: CryptoKey, recovery: boolean) => {
    const registration = await signObject(sigPrivate, {
      type: REGISTRATION, subject_id: subjectId!, enc_public_key: encPublic, sig_public_key: sigPublic,
      created_at: new Date().toISOString(),
    });
    if (kind === "doctor") {
      await api.post("/e2e/keys/doctor", { registration, recovery }, me!.institution_id as Service);
    } else {
      await api.post("/e2e/patient-keys", { registration });
    }
  }, [kind, me, subjectId]);

  const setup = useCallback(async (passphrase: string, recovery = false) => {
    if (!me || !kind) throw new Error("This account does not hold keys");
    if (passphrase.length < MIN_PASSPHRASE) throw new Error(`Use a passphrase of at least ${MIN_PASSPHRASE} characters`);
    const encPair = await generateEncryptionKeyPair();
    const sigPair = await generateSigningKeyPair();
    const encPublic = await exportSpki(encPair.publicKey);
    const sigPublic = await exportSpki(sigPair.publicKey);
    const rec: DeviceKeyRecord = {
      subject: me.id, kind, enc_public: encPublic, sig_public: sigPublic,
      enc_blob: await sealWithPassphrase(passphrase, await exportPkcs8(encPair.privateKey)),
      sig_blob: await sealWithPassphrase(passphrase, await exportPkcs8(sigPair.privateKey)),
      created_at: new Date().toISOString(),
    };
    await register(encPublic, sigPublic, sigPair.privateKey, recovery);
    await saveDeviceKeys(rec);
    setRecord(rec);
    await activate(rec, passphrase);
  }, [activate, kind, me, register]);

  const unlock = useCallback(async (passphrase: string) => {
    if (!record) throw new Error("No device key on this browser");
    try {
      await activate(record, passphrase);
    } catch (err) {
      void api.post("/e2e/client-events", { action: "keys.device_unlock_failed", target_type: "device_key",
        target_id: subjectId ?? "?", detail: { reason: "unlock failed" } }).catch(() => undefined);
      throw err;
    }
  }, [activate, record, subjectId]);

  const lock = useCallback(() => {
    setKeys(null);
    setStatus(record ? "locked" : "none");
  }, [record]);

  const downloadBackup = useCallback(() => {
    if (!record) return;
    const url = URL.createObjectURL(backupFile(record));
    const a = document.createElement("a");
    a.href = url;
    a.download = `device-key-backup-${record.kind}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [record]);

  const restore = useCallback(async (fileText: string, passphrase: string) => {
    if (!me) return;
    const rec = parseBackup(fileText, me.id);
    await openWithPassphrase(passphrase, rec.enc_blob); // the passphrase must open it before it replaces anything
    await saveDeviceKeys(rec);
    setRecord(rec);
    await activate(rec, passphrase);
  }, [activate, me]);

  const groupKey = useCallback((hospital: string, department: string, version: number) =>
    keys?.groups.get(`${hospital}|${department}|${version}`) ?? null, [keys]);

  const refresh = useCallback(async () => {
    if (!keys) return;
    const { state, dir } = await serverState(keys.encKeyId);
    const row = dir?.entries.find((r) => r.entry.enc_key_id === keys.encKeyId && !r.revoked);
    const entry = row ? await verifiedEntry(row).catch(() => null) : null;
    const groups = kind === "doctor" ? await loadGroups(dir, keys.encPrivate, keys.encKeyId) : keys.groups;
    setKeys({ ...keys, entry, groups });
    setKeyState(state);
  }, [keys, kind, loadGroups, serverState]);

  const value = useMemo<DeviceKeys>(() => ({
    status, kind, subjectId, record, keys, keyState, setup, unlock, lock, downloadBackup, restore, groupKey, refresh,
  }), [status, kind, subjectId, record, keys, keyState, setup, unlock, lock, downloadBackup, restore, groupKey, refresh]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDeviceKeys(): DeviceKeys {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDeviceKeys outside DeviceKeysProvider");
  return ctx;
}
