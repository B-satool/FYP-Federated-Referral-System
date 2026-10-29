/**
 * Device storage for this browser (IndexedDB): the user's private keys, sealed with their passphrase
 * (PBKDF2-SHA-256 600k + AES-256-GCM), and the patient's local referral copies (WP10). Nothing here is sent to
 * the platform. Clearing the browser's site data removes it; the backup file (passphrase-protected) restores it.
 */
import type { DirectoryEntry, PassphraseBlob } from "./suite";

export type DeviceKeyRecord = {
  subject: string; // account subject (Keycloak sub)
  kind: "doctor" | "patient";
  enc_public: string;
  sig_public: string;
  // Automatic device keys (2026-10-30): the private keys themselves, created non-extractable in this browser and
  // stored by IndexedDB as CryptoKey objects. They can be used here but never read out, even by this app's own code.
  enc_key?: CryptoKey;
  sig_key?: CryptoKey;
  // Earlier passphrase-sealed keys (PKCS#8, PBKDF2 + AES-GCM), still opened with the passphrase if present
  enc_blob?: PassphraseBlob;
  sig_blob?: PassphraseBlob;
  created_at: string;
  entry?: DirectoryEntry | null; // the signed directory entry once issued
};

const DB_NAME = "refx-device";
const DB_VERSION = 1;

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("keys")) db.createObjectStore("keys", { keyPath: "subject" });
      if (!db.objectStoreNames.contains("copies")) db.createObjectStore("copies", { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(store: string, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const req = fn(t.objectStore(store));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const loadDeviceKeys = (subject: string) =>
  tx<DeviceKeyRecord | undefined>("keys", "readonly", (s) => s.get(subject) as IDBRequest<DeviceKeyRecord | undefined>);
export const saveDeviceKeys = (rec: DeviceKeyRecord) => tx("keys", "readwrite", (s) => s.put(rec));
export const deleteDeviceKeys = (subject: string) => tx("keys", "readwrite", (s) => s.delete(subject));

/** The patient's own copies of referral bundles (still ciphertext, with the data keys wrapped to the patient). */
export type LocalCopy = { id: string; subject: string; reference: string; saved_at: string; bundle: unknown };
export const saveCopy = (c: LocalCopy) => tx("copies", "readwrite", (s) => s.put(c));
export const listCopies = async (subject: string): Promise<LocalCopy[]> =>
  (await tx<LocalCopy[]>("copies", "readonly", (s) => s.getAll() as IDBRequest<LocalCopy[]>)).filter((c) => c.subject === subject);
export const deleteCopy = (id: string) => tx("copies", "readwrite", (s) => s.delete(id));

/** A backup file holds only the sealed blobs and public keys; the passphrase is still needed to use it. */
export function backupFile(rec: DeviceKeyRecord): Blob {
  return new Blob([JSON.stringify({ format: "refx-device-key-backup/v1", ...rec }, null, 2)], { type: "application/json" });
}

export function parseBackup(text: string, subject: string): DeviceKeyRecord {
  const data = JSON.parse(text);
  if (data.format !== "refx-device-key-backup/v1") throw new Error("This is not a device key backup file");
  if (data.subject !== subject) throw new Error("This backup belongs to a different account");
  const { format: _f, ...rec } = data;
  return rec as DeviceKeyRecord;
}
