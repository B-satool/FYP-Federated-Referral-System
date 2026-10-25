import { ReactNode, useState } from "react";
import { Link as RouterLink, NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Box, Button, Container, Divider, Drawer, IconButton, Link, Stack, Typography, useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import MenuIcon from "@mui/icons-material/Menu";
import CloseIcon from "@mui/icons-material/Close";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { actionableCount, Queue } from "../features/workqueue/queue";
import { hasRole, useMe } from "../hooks";
import { tokens } from "../theme";
import { Brand } from "./Brand";

type NavItem = { to: string; label: string; show: boolean; badge?: number };
type NavGroup = { title: string; items: NavItem[] };

const ROLE_LABELS: Record<string, string> = {
  clinician: "Doctor",
  clinic_staff: "Staff",
  diagnostics_staff: "Laboratory / imaging staff",
  institution_admin: "Administrator",
  rule_reviewer: "Clinical rule reviewer",
};

function roleText(roles: string[]): string {
  return roles
    .filter((r) => r in ROLE_LABELS)
    .map((r) => ROLE_LABELS[r])
    .join(", ");
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { logout } = useAuth();
  const { data: me } = useMe();
  const kind = me?.institution_kind;
  const doctor = hasRole(me, "clinician");
  const staff = hasRole(me, "clinic_staff");
  const refers = (doctor || staff) && kind !== "laboratory";
  const hasQueue = doctor || staff;
  const queue = useQuery({ queryKey: ["work-queue"], queryFn: () => api.get<Queue>("/work-queue"), enabled: hasQueue, refetchInterval: 30000, staleTime: 15000 });
  const open = actionableCount(queue.data);

  const groups: NavGroup[] = [
    {
      title: "Work",
      items: [
        { to: "/work-queue", label: "Work queue", show: hasQueue, badge: open },
        { to: "/referrals/new", label: "New referral", show: doctor && kind !== "laboratory" },
        { to: "/referrals", label: "Referrals", show: refers },
        { to: "/incoming", label: "Incoming referrals", show: doctor && kind === "hospital" },
        { to: "/patient-links", label: "Patient link requests", show: hasRole(me, "clinic_staff", "institution_admin") },
        { to: "/orders", label: "Test and scan orders", show: hasRole(me, "diagnostics_staff") },
      ],
    },
    {
      title: "Rules",
      items: [
        { to: "/rules", label: "Medication rules", show: doctor || hasRole(me, "rule_reviewer") },
        { to: "/medicine-names", label: "Medicine names", show: doctor || staff || hasRole(me, "rule_reviewer") },
      ],
    },
    {
      title: "Administration",
      items: [
        { to: "/admin/users", label: "Accounts", show: hasRole(me, "institution_admin") },
        { to: "/admin/access", label: "Source access", show: hasRole(me, "institution_admin") && kind !== "platform" },
        { to: "/admin/audit", label: "Audit log", show: hasRole(me, "institution_admin") },
      ],
    },
  ];

  return (
    <Stack className="on-dark" sx={{ height: "100%", color: tokens.navText, p: 2 }}>
      <Box sx={{ px: 0.5, py: 1 }}>
        <Brand onDark />
      </Box>
      <Box component="nav" aria-label="Main" sx={{ mt: 2, flexGrow: 1, overflowY: "auto" }}>
        {groups
          .map((g) => ({ ...g, items: g.items.filter((i) => i.show) }))
          .filter((g) => g.items.length > 0)
          .map((g) => (
            <Box key={g.title} sx={{ mb: 2.5 }}>
              <Typography variant="overline" component="div" sx={{ color: tokens.navMuted, px: 1.5, mb: 0.5 }}>
                {g.title}
              </Typography>
              <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
                {g.items.map((i) => (
                  <li key={i.to}>
                    <Box
                      component={NavLink}
                      to={i.to}
                      onClick={onNavigate}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 1,
                        minHeight: 40,
                        px: 1.5,
                        borderRadius: 1,
                        color: tokens.navText,
                        textDecoration: "none",
                        fontWeight: 500,
                        border: "1px solid transparent",
                        "&:hover": { backgroundColor: tokens.navActive },
                        "&.active": { backgroundColor: tokens.navActive, fontWeight: 700, borderColor: tokens.navMuted },
                      }}
                    >
                      <span>{i.label}</span>
                      {!!i.badge && (
                        <Box component="span" sx={{ minWidth: 24, px: 0.75, textAlign: "center", borderRadius: 1, backgroundColor: tokens.focusOnDark, color: tokens.ink, fontSize: "0.8125rem", fontWeight: 700 }}>
                          {i.badge}
                          <span className="sr-only"> open items</span>
                        </Box>
                      )}
                    </Box>
                  </li>
                ))}
              </Box>
            </Box>
          ))}
      </Box>
      <Divider sx={{ borderColor: tokens.navActive, my: 1.5 }} />
      {me && (
        <Stack spacing={1.25}>
          <Box sx={{ px: 0.5 }}>
            <Typography sx={{ fontWeight: 600, color: "inherit", overflowWrap: "anywhere" }}>{me.name}</Typography>
            <Typography variant="body2" sx={{ color: tokens.navMuted }}>
              {me.institution_name}
              {me.department_name ? `, ${me.department_name}` : ""}
            </Typography>
            <Typography variant="body2" sx={{ color: tokens.navMuted }}>
              {roleText(me.roles)}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            onClick={() => logout()}
            sx={{ color: tokens.navText, borderColor: tokens.navMuted, "&:hover": { backgroundColor: tokens.navActive, borderColor: tokens.navText } }}
          >
            Sign out
          </Button>
        </Stack>
      )}
    </Stack>
  );
}

export function Footer() {
  return (
    <Box component="footer" sx={{ borderTop: `1px solid ${tokens.line}`, mt: 4 }}>
      <Container maxWidth="xl" sx={{ py: 2.5 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
          <Typography variant="body2" color="text.secondary">
            © {new Date().getFullYear()} Referral Preparation and Follow-through Platform. Final year project prototype, synthetic data only.
          </Typography>
          <Stack component="nav" aria-label="Policies" direction="row" spacing={2.5} flexWrap="wrap" useFlexGap>
            <Link component={RouterLink} to="/privacy">
              Privacy notice
            </Link>
            <Link component={RouterLink} to="/terms">
              Terms of use
            </Link>
            <Link component={RouterLink} to="/accessibility">
              Accessibility
            </Link>
          </Stack>
        </Stack>
      </Container>
    </Box>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"), { noSsr: true });
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      {desktop ? (
        <Box component="aside" sx={{ width: 272, flexShrink: 0, backgroundColor: tokens.nav, position: "sticky", top: 0, height: "100vh" }}>
          <SidebarContent />
        </Box>
      ) : (
        <Drawer open={menuOpen} onClose={() => setMenuOpen(false)} PaperProps={{ sx: { width: 288, maxWidth: "88vw", backgroundColor: tokens.nav, backgroundImage: "none" } }}>
          <Box sx={{ display: "flex", justifyContent: "flex-end", p: 1, pb: 0 }} className="on-dark">
            <IconButton aria-label="Close menu" onClick={() => setMenuOpen(false)} sx={{ color: tokens.navText, "&:hover": { backgroundColor: tokens.navActive } }}>
              <CloseIcon />
            </IconButton>
          </Box>
          <Box sx={{ flexGrow: 1, minHeight: 0 }}>
            <SidebarContent onNavigate={() => setMenuOpen(false)} />
          </Box>
        </Drawer>
      )}
      <Box sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        {!desktop && (
          <Box sx={{ position: "sticky", top: 0, zIndex: 1100, display: "flex", alignItems: "center", gap: 1, px: 1.5, height: 60, backgroundColor: tokens.surface, borderBottom: `1px solid ${tokens.line}` }}>
            <IconButton aria-label="Open menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}>
              <MenuIcon />
            </IconButton>
            <Brand />
          </Box>
        )}
        <Container component="main" id="main" tabIndex={-1} maxWidth="xl" sx={{ flex: 1, py: { xs: 2, md: 3.5 }, "&:focus": { outline: "none" } }}>
          {children}
        </Container>
        <Footer />
      </Box>
    </Box>
  );
}
