import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, Service } from "./api/client";
import type { Me, ReferenceData } from "./api/types";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/me"), staleTime: 60_000 });
}

export function useRefData() {
  return useQuery({ queryKey: ["reference-data"], queryFn: () => api.get<ReferenceData>("/reference-data"), staleTime: 300_000 });
}

export function hasRole(me: Me | undefined, ...roles: string[]): boolean {
  return !!me && roles.some((r) => me.roles.includes(r));
}

/** Doctor: requests referrals, acknowledges flags; at a hospital also receives referrals for their department. */
export const isDoctor = (me: Me | undefined) => hasRole(me, "clinician");
/** Staff: patient links, records, papers and medicines; send referrals; follow-up. */
export const isStaff = (me: Me | undefined) => hasRole(me, "clinic_staff");
/** Laboratory, imaging or ECG staff: test and scan orders. */
export const isDiagnostics = (me: Me | undefined) => hasRole(me, "diagnostics_staff");

/** The signed-in user's own institution system (for its own patient index, inbox or orders). */
export function ownService(me: Me | undefined): Service {
  return (me?.institution_id ?? "central") as Service;
}

/** Sets the browser tab title so each screen is identifiable in history and tabs. */
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} | Referral Platform` : "Referral Platform";
  }, [title]);
}
