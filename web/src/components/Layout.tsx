import { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { AppBar, Box, Button, Chip, Container, Stack, Toolbar, Typography } from "@mui/material";
import LocalHospital from "@mui/icons-material/LocalHospital";
import { useAuth } from "../auth/AuthProvider";
import { hasRole, useMe } from "../hooks";

type NavItem = { to: string; label: string; show: boolean };

export function Layout({ children }: { children: ReactNode }) {
  const { logout } = useAuth();
  const { data: me } = useMe();
  const loc = useLocation();
  const kind = me?.institution_kind;
  const clinicUser = kind === "clinic" && hasRole(me, "clinic_staff", "clinician");
  const items: NavItem[] = [
    { to: "/referrals", label: "Referrals", show: clinicUser },
    { to: "/work-queue", label: "Work queue", show: hasRole(me, "clinic_staff", "clinician", "lab_staff") },
    { to: "/patient-links", label: "Patient links", show: kind === "clinic" && hasRole(me, "clinic_staff", "clinician", "institution_admin") },
    { to: "/rules", label: "Medication rules", show: clinicUser || hasRole(me, "rule_reviewer") },
    { to: "/specialist", label: "Specialist inbox", show: hasRole(me, "specialist") },
    { to: "/lab", label: "Laboratory records", show: hasRole(me, "lab_staff") },
    { to: "/admin/users", label: "Accounts", show: hasRole(me, "institution_admin") },
    { to: "/admin/access", label: "Source access", show: hasRole(me, "institution_admin") && kind !== "platform" },
    { to: "/admin/audit", label: "Audit log", show: hasRole(me, "institution_admin") },
  ];
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <AppBar position="static" elevation={1} color="primary">
        <Toolbar sx={{ gap: 2, flexWrap: "wrap" }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LocalHospital aria-hidden />
            <Typography variant="h6" component="div" sx={{ whiteSpace: "nowrap" }}>
              Referral Platform
            </Typography>
          </Stack>
          <Box component="nav" aria-label="Main" sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, flexGrow: 1 }}>
            {items
              .filter((i) => i.show)
              .map((i) => (
                <Button
                  key={i.to}
                  component={NavLink}
                  to={i.to}
                  color="inherit"
                  sx={{ opacity: loc.pathname.startsWith(i.to) ? 1 : 0.8, borderBottom: loc.pathname.startsWith(i.to) ? "2px solid white" : "2px solid transparent", borderRadius: 0 }}
                >
                  {i.label}
                </Button>
              ))}
          </Box>
          {me && (
            <Stack direction="row" spacing={1} alignItems="center">
              <Box sx={{ textAlign: "right" }}>
                <Typography variant="body2">{me.name}</Typography>
                <Typography variant="caption" sx={{ opacity: 0.85 }}>
                  {me.institution_name}
                </Typography>
              </Box>
              <Chip size="small" label={me.roles.filter((r) => !r.startsWith("default") && !["offline_access", "uma_authorization"].includes(r)).join(", ")} sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "white" }} />
              <Button color="inherit" variant="outlined" size="small" onClick={() => logout()}>
                Sign out
              </Button>
            </Stack>
          )}
        </Toolbar>
      </AppBar>
      <Box sx={{ bgcolor: "warning.light", py: 0.25, textAlign: "center" }}>
        <Typography variant="caption">Prototype with synthetic data only. Not for clinical use.</Typography>
      </Box>
      <Container component="main" id="main" maxWidth="xl" sx={{ py: 3 }}>
        {children}
      </Container>
    </Box>
  );
}
