import { ReactNode } from "react";
import { Link as RouterLink, Navigate, Route, Routes } from "react-router-dom";
import { Alert, Box, Container, Link } from "@mui/material";
import { useAuth } from "./auth/AuthProvider";
import { Brand } from "./components/Brand";
import { Footer, Layout } from "./components/Layout";
import { ErrorAlert, Loading } from "./components/common";
import { hasRole, useMe } from "./hooks";
import { SignIn } from "./features/auth/SignIn";
import { NotFound } from "./features/auth/NotFound";
import { AccessibilityStatement, PrivacyNotice, TermsOfUse } from "./features/legal/LegalPages";
import { ReferralList } from "./features/referrals/ReferralList";
import { NewReferral } from "./features/referrals/NewReferral";
import { ReferralWorkspace } from "./features/referrals/ReferralWorkspace";
import { DocumentReview } from "./features/documents/DocumentReview";
import { WorkQueue } from "./features/workqueue/WorkQueue";
import { PatientLinks } from "./features/identity/PatientLinks";
import { RulesPage } from "./features/rules/RulesPage";
import { MedicineNames } from "./features/rules/MedicineNames";
import { IncomingCase, IncomingList } from "./features/incoming/Incoming";
import { OrderList, OrderView } from "./features/orders/Orders";
import { AdminUsers } from "./features/admin/AdminUsers";
import { SourceAccess } from "./features/admin/SourceAccess";
import { AuditLog } from "./features/admin/AuditLog";

function Home() {
  const { data: me, isLoading, error } = useMe();
  if (isLoading) return <Loading />;
  if (error) return <ErrorAlert error={error} />;
  if (hasRole(me, "clinic_staff", "clinician")) return <Navigate to="/work-queue" replace />;
  if (hasRole(me, "diagnostics_staff")) return <Navigate to="/orders" replace />;
  if (hasRole(me, "rule_reviewer")) return <Navigate to="/rules" replace />;
  if (hasRole(me, "institution_admin")) return <Navigate to="/admin/users" replace />;
  return <Alert severity="info">Your account has no role in this application. Ask your institution administrator to assign one.</Alert>;
}

/** Policy pages are readable before signing in, with a minimal frame instead of the signed-in navigation. */
function PublicFrame({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Container maxWidth="lg" sx={{ flex: 1, py: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 4 }}>
          <Brand />
          <Link component={RouterLink} to="/">
            Back to sign in
          </Link>
        </Box>
        {children}
      </Container>
      <Footer />
    </Box>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Signing in…" />;
  if (!user) {
    return (
      <Routes>
        <Route path="/privacy" element={<PublicFrame><PrivacyNotice /></PublicFrame>} />
        <Route path="/terms" element={<PublicFrame><TermsOfUse /></PublicFrame>} />
        <Route path="/accessibility" element={<PublicFrame><AccessibilityStatement /></PublicFrame>} />
        <Route path="*" element={<SignIn />} />
      </Routes>
    );
  }
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/callback" element={<Home />} />
        <Route path="/work-queue" element={<WorkQueue />} />
        <Route path="/referrals" element={<ReferralList />} />
        <Route path="/referrals/new" element={<NewReferral />} />
        <Route path="/referrals/:id" element={<ReferralWorkspace />} />
        <Route path="/documents/:id" element={<DocumentReview />} />
        <Route path="/patient-links" element={<PatientLinks />} />
        <Route path="/incoming" element={<IncomingList />} />
        <Route path="/incoming/:id" element={<IncomingCase />} />
        <Route path="/orders" element={<OrderList />} />
        <Route path="/orders/:id" element={<OrderView />} />
        <Route path="/rules" element={<RulesPage />} />
        <Route path="/medicine-names" element={<MedicineNames />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/access" element={<SourceAccess />} />
        <Route path="/admin/audit" element={<AuditLog />} />
        <Route path="/privacy" element={<PrivacyNotice />} />
        <Route path="/terms" element={<TermsOfUse />} />
        <Route path="/accessibility" element={<AccessibilityStatement />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
