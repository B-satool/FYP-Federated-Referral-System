import { Alert, Box, Button, Container, Link, Paper, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { Brand } from "../../components/Brand";
import { Footer } from "../../components/Layout";
import { usePageTitle } from "../../hooks";

const STAGES: [string, string][] = [
  ["Prepare", "Create the referral and confirm which patient it is about."],
  ["Gather", "Retrieve permitted records from the clinic, laboratory and specialist systems and read uploaded paper records."],
  ["Verify", "Confirm current medications, review medication flags and resolve missing or conflicting information."],
  ["Approve and send", "A clinician approves one exact version of the brief and sends it to the specialist."],
  ["Specialist review", "The specialist acknowledges the referral, reviews the flags and returns a response."],
  ["Follow up", "The clinic reviews the response, completes follow-up tasks and closes the referral."],
];

export function SignIn() {
  const { login } = useAuth();
  usePageTitle("Sign in");
  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Container maxWidth="lg" sx={{ flex: 1, py: { xs: 3, md: 6 } }}>
        <Box sx={{ mb: { xs: 3, md: 5 } }}>
          <Brand />
        </Box>
        <Stack direction={{ xs: "column", md: "row" }} spacing={{ xs: 4, md: 8 }} alignItems={{ md: "flex-start" }}>
          <Box sx={{ flex: 1.2 }}>
            <Typography variant="h4" component="h1" gutterBottom>
              Referral Preparation and Follow-through Platform
            </Typography>
            <Typography color="text.secondary" sx={{ maxWidth: 620, mb: 3 }}>
              Prepare a verified referral package, highlight medications that matter for the planned procedure, send it to a specialist and track the response until follow-up is complete.
            </Typography>
            <Typography variant="h6" component="h2" gutterBottom>
              How a referral moves through the platform
            </Typography>
            <Box component="ol" sx={{ m: 0, p: 0, listStyle: "none", maxWidth: 640 }}>
              {STAGES.map(([name, text], i) => (
                <Box component="li" key={name} sx={{ display: "flex", gap: 1.5, py: 1.25, borderTop: i === 0 ? "none" : "1px solid", borderColor: "divider" }}>
                  <Box aria-hidden sx={{ width: 28, height: 28, flexShrink: 0, display: "grid", placeItems: "center", borderRadius: 1, backgroundColor: "primary.main", color: "primary.contrastText", fontWeight: 700, fontSize: "0.875rem" }}>
                    {i + 1}
                  </Box>
                  <Box>
                    <Typography sx={{ fontWeight: 600 }} component="span" display="block">
                      {name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" component="span" display="block">
                      {text}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
          <Paper component="section" aria-labelledby="signin-title" sx={{ flex: 0.9, p: 3, maxWidth: { md: 420 }, width: "100%" }}>
            <Stack spacing={2}>
              <Typography variant="h6" component="h2" id="signin-title">
                Sign in
              </Typography>
              <Typography color="text.secondary">You will be taken to your institution's sign-in page and returned here afterwards.</Typography>
              <Alert severity="warning">Prototype using synthetic data only. Not for clinical use.</Alert>
              <Button variant="contained" size="large" onClick={() => login()}>
                Sign in with your institution account
              </Button>
              <Typography variant="caption" color="text.secondary">
                By signing in you agree to the{" "}
                <Link component={RouterLink} to="/terms">
                  terms of use
                </Link>{" "}
                and have read the{" "}
                <Link component={RouterLink} to="/privacy">
                  privacy notice
                </Link>
                .
              </Typography>
            </Stack>
          </Paper>
        </Stack>
      </Container>
      <Footer />
    </Box>
  );
}
