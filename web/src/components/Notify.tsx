import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { Alert, Snackbar } from "@mui/material";

type Notice = { message: string; severity: "success" | "error"; key: number };
type Notify = (message: string, severity?: Notice["severity"]) => void;

const NotifyContext = createContext<Notify>(() => undefined);

// Lets code outside React (the query client's mutation cache) raise a confirmation.
let registered: Notify = () => undefined;
export const notifyOutsideReact: Notify = (message, severity) => registered(message, severity);

export const useNotify = () => useContext(NotifyContext);

/**
 * Confirmation messages for completed actions. The region is announced politely
 * to screen readers and ignores pointer events so it never covers a control.
 */
export function NotifyProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<Notice | null>(null);
  const notify = useCallback<Notify>((message, severity = "success") => setNotice({ message, severity, key: Date.now() }), []);
  useEffect(() => {
    registered = notify;
    return () => {
      registered = () => undefined;
    };
  }, [notify]);
  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <Snackbar
        key={notice?.key}
        open={!!notice}
        autoHideDuration={4500}
        onClose={(_, reason) => reason !== "clickaway" && setNotice(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        sx={{ pointerEvents: "none" }}
      >
        {notice ? (
          <Alert role="status" aria-live="polite" severity={notice.severity} variant="outlined" sx={{ pointerEvents: "none", minWidth: 220 }}>
            {notice.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </NotifyContext.Provider>
  );
}
