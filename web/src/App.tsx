import { Navigate, Route, Routes } from "react-router-dom";
import { Alert, Box, Button, Paper, Stack, Typography } from "@mui/material";
import { useAuth } from "./auth/AuthProvider";
import { Layout } from "./components/Layout";
import { ErrorAlert, Loading } from "./components/common";
import { hasRole, useMe } from "./hooks";
import { ReferralList } from "./features/referrals/ReferralList";
import { NewReferral } from "./features/referrals/NewReferral";
import { ReferralWorkspace } from "./features/referrals/ReferralWorkspace";
import { DocumentReview } from "./features/documents/DocumentReview";
import { WorkQueue } from "./features/workqueue/WorkQueue";
import { PatientLinks } from "./features/identity/PatientLinks";
import { RulesReview } from "./features/rules/RulesReview";
import { SpecialistInbox } from "./features/specialist/SpecialistInbox";
import { SpecialistCase } from "./features/specialist/SpecialistCase";
import { LabWorkspace } from "./features/lab/LabWorkspace";
import { AdminUsers } from "./features/admin/AdminUsers";
import { SourceAccess } from "./features/admin/SourceAccess";
import { AuditLog } from "./features/admin/AuditLog";

function Home() {
  const { data: me, isLoading, error } = useMe();
  if (isLoading) return <Loading />;
  if (error) return <ErrorAlert error={error} />;
  if (hasRole(me, "specialist")) return <Navigate to="/specialist" replace />;
  if (hasRole(me, "lab_staff")) return <Navigate to="/work-queue" replace />;
  if (hasRole(me, "clinic_staff", "clinician")) return <Navigate to="/referrals" replace />;
  if (hasRole(me, "rule_reviewer")) return <Navigate to="/rules" replace />;
  if (hasRole(me, "institution_admin")) return <Navigate to="/admin/users" replace />;
  return <Alert severity="info">Your account has no role in this application.</Alert>;
}

function SignIn() {
  const { login } = useAuth();
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", bgcolor: "grey.100", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 520 }}>
        <Stack spacing={2}>
          <Typography variant="h4" component="h1">
            Referral Preparation and Follow-through Platform
          </Typography>
          <Typography color="text.secondary">
            Prepare verified referral packages, highlight referral-specific medication flags, share them with a specialist
            and track the response and follow-up.
          </Typography>
          <Alert severity="warning">Prototype using synthetic data only. Not for clinical use.</Alert>
          <Button variant="contained" size="large" onClick={() => login()}>
            Sign in with your institution account
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Signing in…" />;
  if (!user) return <SignIn />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/callback" element={<Home />} />
        <Route path="/referrals" element={<ReferralList />} />
        <Route path="/referrals/new" element={<NewReferral />} />
        <Route path="/referrals/:id" element={<ReferralWorkspace />} />
        <Route path="/documents/:id" element={<DocumentReview />} />
        <Route path="/work-queue" element={<WorkQueue />} />
        <Route path="/patient-links" element={<PatientLinks />} />
        <Route path="/rules" element={<RulesReview />} />
        <Route path="/specialist" element={<SpecialistInbox />} />
        <Route path="/specialist/cases/:id" element={<SpecialistCase />} />
        <Route path="/lab" element={<LabWorkspace />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/access" element={<SourceAccess />} />
        <Route path="/admin/audit" element={<AuditLog />} />
        <Route path="*" element={<Alert severity="info">Page not found.</Alert>} />
      </Routes>
    </Layout>
  );
}
