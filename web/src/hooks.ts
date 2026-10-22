import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
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

/** Sets the browser tab title so each screen is identifiable in history and tabs. */
export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} | Referral Platform` : "Referral Platform";
  }, [title]);
}
