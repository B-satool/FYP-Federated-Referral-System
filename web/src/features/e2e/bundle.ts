/** The medication data bundle (GET /med-bundle), checked on this device: its SHA-256 over canonical JSON must match
 * the published hash before any flag is computed from it (spec v4 9.1). */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { canonicalJson, sha256Hex } from "../../crypto/suite";
import type { Bundle } from "./flags";

export class BundleIntegrityError extends Error {}

export async function fetchBundle(): Promise<Bundle> {
  const b = await api.get<Bundle>("/med-bundle");
  const digest = await sha256Hex(canonicalJson(b.content));
  if (digest !== b.sha256 || b.content.type !== "refx.med-bundle/v1") {
    throw new BundleIntegrityError("The medication data did not pass its integrity check, so no flags were computed");
  }
  return b;
}

export function useMedBundle() {
  return useQuery({ queryKey: ["med-bundle"], queryFn: fetchBundle, staleTime: 30 * 60_000, gcTime: 60 * 60_000 });
}
