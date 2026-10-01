import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { User, UserManager, WebStorageStateStore } from "oidc-client-ts";

// Browser sign-in uses the OIDC authorization-code flow with PKCE (public client, no secret).
// Showing or hiding screens by role is a convenience only; every service enforces access itself.
const authority = import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/realms/referral";

export const userManager = new UserManager({
  authority,
  client_id: "referral-web",
  redirect_uri: `${window.location.origin}/callback`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: "openid profile email",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
});

type AuthState = {
  user: User | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (window.location.pathname === "/callback") {
          const u = await userManager.signinRedirectCallback();
          const target = (u.state as string | undefined) ?? "/";
          window.history.replaceState({}, "", target);
          if (!cancelled) setUser(u);
        } else {
          const u = await userManager.getUser();
          if (!cancelled) setUser(u && !u.expired ? u : null);
        }
      } catch (err) {
        console.error("sign-in failed", err);
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    const onLoaded = (u: User) => setUser(u);
    const onUnloaded = () => setUser(null);
    userManager.events.addUserLoaded(onLoaded);
    userManager.events.addUserUnloaded(onUnloaded);
    userManager.events.addSilentRenewError(() => setUser(null));
    return () => {
      cancelled = true;
      userManager.events.removeUserLoaded(onLoaded);
      userManager.events.removeUserUnloaded(onUnloaded);
    };
  }, []);

  const login = useCallback(
    () => userManager.signinRedirect({ state: window.location.pathname + window.location.search }),
    [],
  );
  const logout = useCallback(async () => {
    await userManager.signoutRedirect();
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export async function currentToken(): Promise<string | null> {
  const u = await userManager.getUser();
  if (!u) return null;
  if (u.expires_in !== undefined && u.expires_in < 20) {
    try {
      const renewed = await userManager.signinSilent();
      return renewed?.access_token ?? null;
    } catch {
      return null;
    }
  }
  return u.access_token;
}
