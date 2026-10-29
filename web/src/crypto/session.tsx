/**
 * The signed-in user's device keys (spec v4 5.3), set up and unlocked automatically.
 *
 * "Your login proves who you are; your device key decrypts the data." The first time a doctor or patient signs in on a
 * browser, it creates their key pairs there, non-extractable (they can be used in this browser but never read out,
 * even by this app), stores them in IndexedDB and registers the public halves: the doctor's hospital signs them by
 * policy, the platform signs a patient's. On every later visit they are loaded and used with no prompt. Nothing private
 * leaves the browser. Doctors also receive their departments' group keys, wrapped to their own key.
 *
 * Signing in on another browser or device creates a key there, which replaces the earlier one (the hospital revokes it
 * and tells its administrators). Records from institutions can be requested again for the new key; items that existed
 * only on the platform stay readable only with the old key (or from the patient's copy).
 */
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, Service } from "../api/client";
import { useMe, hasRole } from "../hooks";
import { DirectoryRow, verifiedEntry } from "./directory";
import { DeviceKeyRecord, loadDeviceKeys, saveDeviceKeys } from "./keystore";
import {
  DirectoryEntry, exportSpki, generateDeviceKeyPairs, groupContext, importEncPrivate, keyId, publicFromPkcs8, signObject,
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

/** loading: not known yet; preparing: creating or loading this device's key; failed: could not (retry offered) */
type Status = "loading" | "unavailable" | "preparing" | "failed" | "unlocked";

type DeviceKeys = {
  status: Status;
  kind: "doctor" | "patient" | null;
  subjectId: string | null;
  record: DeviceKeyRecord | null;
  keys: UnlockedKeys | null;
  /** server-side state of the key: active (signed), pending (waits for an administrator), revoked, or none */
  keyState: string | null;
  error: string | null;
  /** create a new key on this device (replacing any other); runs automatically, offered again after a failure */
  setup: (recovery?: boolean) => Promise<void>;
  groupKey: (hospital: string, department: string, version: number) => CryptoKey | null;
  refresh: () => Promise<void>;
};

const Ctx = createContext<DeviceKeys | null>(null);
const REGISTRATION = "refx.key.registration/v1";

type MyDirectory = {
  subject_id: string;
  entries: DirectoryRow[];
  group_wraps: { hospital_id: string; department: string; group_version: number; member_key_id: string; wrapped: Wrapped }[];
};

/** One tab at a time creates a key, so two tabs opened together do not register two keys. */
function withDeviceLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = (navigator as Navigator & { locks?: { request: (name: string, cb: () => Promise<T>) => Promise<T> } }).locks;
  return locks ? locks.request("refx-device-key", fn) : fn();
}

export function DeviceKeysProvider({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const kind = hasRole(me, "patient") ? "patient" : hasRole(me, "clinician") ? "doctor" : null;
  const subjectId = me ? (kind === "patient" ? `patient:${me.id}` : me.id) : null;
  const [record, setRecord] = useState<DeviceKeyRecord | null>(null);
  const [keys, setKeys] = useState<UnlockedKeys | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [keyState, setKeyState] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

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
        pkcs8.fill(0);
      } catch {
        /* a wrap that does not open or does not match is ignored */
      }
    }
    return groups;
  }, []);

  const activate = useCallback(async (rec: DeviceKeyRecord) => {
    const encKeyId = await keyId(rec.enc_public);
    const { state, dir } = await serverState(encKeyId);
    const row = dir?.entries.find((r) => r.entry.enc_key_id === encKeyId && !r.revoked);
    const entry = row ? await verifiedEntry(row).catch(() => null) : null;
    const groups = kind === "doctor" ? await loadGroups(dir, rec.enc_key!, encKeyId) : new Map<string, CryptoKey>();
    setKeys({ encPrivate: rec.enc_key!, sigPrivate: rec.sig_key!, encPublic: rec.enc_public, sigPublic: rec.sig_public,
      encKeyId, entry, groups });
    setKeyState(state);
    setStatus("unlocked");
    return state;
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

  const setup = useCallback(async (recovery = false) => {
    if (!me || !kind) throw new Error("This account does not hold keys");
    const { enc, sig } = await generateDeviceKeyPairs();
    const encPublic = await exportSpki(enc.publicKey);
    const sigPublic = await exportSpki(sig.publicKey);
    const rec: DeviceKeyRecord = { subject: me.id, kind, enc_public: encPublic, sig_public: sigPublic,
      enc_key: enc.privateKey, sig_key: sig.privateKey, created_at: new Date().toISOString() };
    await register(encPublic, sigPublic, sig.privateKey, recovery);
    await saveDeviceKeys(rec);
    setRecord(rec);
    await activate(rec);
  }, [activate, kind, me, register]);

  /** Load this browser's key, or create one: no prompt either way. */
  const prepare = useCallback(async () => {
    setStatus("preparing");
    setError(null);
    try {
      await withDeviceLock(async () => {
        const rec = await loadDeviceKeys(me!.id);
        if (rec?.enc_key && rec.sig_key) {
          setRecord(rec);
          const state = await activate(rec);
          if (state === "revoked") await setup(true); // replaced on another device and now used here again
          return;
        }
        // no key in this browser (or only an older passphrase-sealed one): a new key for this device; if this account
        // already has a key elsewhere, the new one replaces it and the hospital's administrators are told
        const dir = await api.get<MyDirectory>("/e2e/directory/me").catch(() => null);
        await setup(!!dir?.entries.some((r) => !r.revoked));
      });
    } catch (e) {
      setStatus("failed");
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [activate, me, setup]);

  useEffect(() => {
    if (!me) return;
    if (!kind || !globalThis.crypto?.subtle || !("indexedDB" in globalThis)) {
      setStatus("unavailable");
      return;
    }
    if (started.current) return;
    started.current = true;
    void prepare();
  }, [me, kind, prepare]);

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
    status, kind, subjectId, record, keys, keyState, error, setup: async (r?: boolean) => {
      setStatus("preparing");
      try { await withDeviceLock(() => setup(r)); } catch (e) { setStatus("failed"); setError(e instanceof Error ? e.message : String(e)); }
    }, groupKey, refresh,
  }), [status, kind, subjectId, record, keys, keyState, error, setup, groupKey, refresh]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDeviceKeys(): DeviceKeys {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDeviceKeys outside DeviceKeysProvider");
  return ctx;
}
