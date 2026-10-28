import { ReactNode } from "react";
import { Alert, Box, Link, Paper, Stack, Typography } from "@mui/material";
import { PageHeader } from "../../components/common";

const contactEmail = import.meta.env.VITE_CONTACT_EMAIL as string | undefined;
const operatorName = import.meta.env.VITE_OPERATOR_NAME as string | undefined;

function Contact() {
  return (
    <>
      <Typography>
        Operator of this deployment: {operatorName || "the institution that hosts it (set by that institution)"}.
      </Typography>
      <Typography>
        Contact:{" "}
        {contactEmail ? <Link href={`mailto:${contactEmail}`}>{contactEmail}</Link> : "the institution administrator named in your account invitation."}
      </Typography>
    </>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box component="section" sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      <Stack spacing={1}>{children}</Stack>
    </Box>
  );
}

function Doc({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <Box sx={{ maxWidth: 860 }}>
      <PageHeader title={title} subtitle={`Last updated ${updated}`} />
      <Alert severity="warning" sx={{ mb: 3 }}>
        This text describes the prototype as built. Before any real patient data is used, the operating institution must review it with its own legal and clinical governance advisers and adopt its own version.
      </Alert>
      <Paper sx={{ p: { xs: 2, md: 3 } }}>{children}</Paper>
    </Box>
  );
}

export function PrivacyNotice() {
  return (
    <Doc title="Privacy notice" updated="22 October 2026">
      <Block title="Who is responsible">
        <Typography>
          This platform is a final year project prototype. For any deployment, the institution that operates it decides why and how data is processed and is responsible for it.
        </Typography>
        <Contact />
      </Block>
      <Block title="Synthetic data only">
        <Typography>The prototype is built and tested with synthetic (invented) patients. Do not enter real patient information into it.</Typography>
      </Block>
      <Block title="What the platform processes">
        <Typography component="div">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Account details: name, username, institution and role, supplied by your institution's sign-in service.</li>
            <li>Referral details: patient identity, reason for referral, priority chosen by a clinician and the planned procedure.</li>
            <li>Records retrieved from the clinic, laboratory and specialist systems, only where your role and that system's own access rules allow it.</li>
            <li>Uploaded paper records, their page images and the text read from them.</li>
            <li>Medication entries, medication flags and who reviewed them.</li>
            <li>Referral briefs, approved package versions, specialist responses and follow-up tasks.</li>
            <li>Audit events: who did what, when, to which record, and the outcome.</li>
          </ul>
        </Typography>
      </Block>
      <Block title="How the data is used">
        <Typography>
          Data is used only to prepare, send and track referrals. It is not sold, used for advertising or passed to analytics services. The platform contains no tracking or analytics scripts.
        </Typography>
      </Block>
      <Block title="Language model assistance">
        <Typography>
          If the operator turns on the optional language model (the prototype supports Anthropic's API), the referral reason and a short text of each retrieved record for one referral are sent to it so it can recommend which records the specialist needs. The recommendation is only a suggestion: staff decide what is sent, the model can never remove a record that is included by default, and every recommendation is recorded with the model and prompt version. The model never creates or changes medication flags. Separately, a small model trained on DDInter's known interactions suggests possible clashes for medicine pairs DDInter does not cover; these travel with the referral labelled "AI suggestion, not verified" and are never flags. If no model is configured, nothing is sent for this purpose and the default selection applies. Whatever model is used, it receives de-identified records only: no name, CNIC, record numbers or date of birth (age and sex instead), with names of doctors and institutions removed and dates given as days before the referral. A model outside this computer (for example Gemma 4 through Ollama's cloud) is used only if the operator has switched that on, and only over an encrypted connection. If the operator chooses Google Cloud Vision to read handwritten papers, the page images are sent to Google; these cannot be de-identified the same way.
        </Typography>
      </Block>
      <Block title="Cookies and browser storage">
        <Typography>
          The platform uses only what is strictly necessary to keep you signed in. Your sign-in token is held in your browser's session storage for the current tab and is cleared when you sign out. The institution's sign-in service may set session cookies for the same purpose. There are no advertising, analytics or preference cookies, so there is no cookie consent banner.
        </Typography>
      </Block>
      <Block title="How long data is kept (provisional)">
        <Typography component="div">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Records retrieved or added for a referral are kept only while the referral needs them: removed 72 hours after the receiving doctor marks the referral complete, straight away if they decline it, and 72 hours after it is cancelled. Once accepted, they are kept for at most 30 days unless the receiving doctor extends this. The receiving hospital's copy of these records is removed at the same time; it keeps its own decision, questions and response. Removal waits until everything sent has been delivered.</li>
            <li>After removal the platform keeps only the referral's reference, a list of what was sent (which record and version, from where, and which flags and rules), the SHA-256 fingerprint of each sent version, and the audit trail. The sending clinic's system keeps its own copy of what was sent, the receiving institution keeps what it received, and the source institutions keep their own records.</li>
            <li>Access that another institution gives to its records is temporary: 14 days by default and at most 30, and it is closed when the referral finishes.</li>
            <li>Audit events and referral events are kept and are append-only.</li>
          </ul>
        </Typography>
        <Typography>The operating institution must confirm these periods before any hosted use.</Typography>
      </Block>
      <Block title="Children's data">
        <Typography>
          Orthodontic referrals often concern patients under 18. In a real deployment the operating institution must obtain and record consent from a parent or guardian, as the law that applies to it requires, before a child's data is entered. This prototype does not collect consent because it uses synthetic data only.
        </Typography>
      </Block>
      <Block title="Access, correction and deletion requests">
        <Typography>
          To ask for access to, correction of, or deletion of data about you, contact the institution that treats you or runs this deployment, using the contact above. Some records, such as approved referral packages and audit events, may need to be kept for clinical, legal or audit reasons. The institution will tell you what it can remove and what it must keep. An institution administrator can disable a staff account, which stops that person's access straight away, including at the source systems.
        </Typography>
      </Block>
      <Block title="Open-source components and fonts">
        <Typography>
          The web interface is built with React, Material UI, TanStack Query, React Router, React Hook Form and oidc-client-ts, all open-source libraries. Text is set in the fonts already installed on your device, so no font files are loaded from other companies' servers.
        </Typography>
      </Block>
    </Doc>
  );
}

export function TermsOfUse() {
  return (
    <Doc title="Terms of use" updated="22 October 2026">
      <Block title="1. What this is">
        <Typography>
          The Referral Preparation and Follow-through Platform is a prototype for study and demonstration. It is not a medical device and must not be used to make or support decisions about real patients.
        </Typography>
      </Block>
      <Block title="2. Your account">
        <Typography>
          Use only your own account and keep your sign-in details private. Screens and actions depend on your role. Every access, correction, approval and submission is written to an audit record that names you.
        </Typography>
      </Block>
      <Block title="3. Clinical responsibility">
        <Typography component="div">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Clinicians verify extracted information, confirm current medication use and approve every referral. Only an approved version is sent.</li>
            <li>Text produced by a language model is a draft until a clinician has reviewed it.</li>
            <li>A medication flag is a prompt to review. It does not advise starting, stopping or changing any medicine and does not set urgency.</li>
            <li>Marking a flag Reviewed records that someone has seen it. It does not mean treatment is cleared.</li>
            <li>No matching flag does not mean treatment is safe, and a source that is unavailable or denied does not mean there is no history.</li>
          </ul>
        </Typography>
      </Block>
      <Block title="4. Acceptable use">
        <Typography>
          Do not enter real patient data, try to bypass access controls, upload files you do not have the right to use or that are harmful, or share your credentials.
        </Typography>
      </Block>
      <Block title="5. Availability">
        <Typography>The prototype is provided as it is, without any promise of availability. Demonstration data may be reset at any time.</Typography>
      </Block>
      <Block title="6. Fees">
        <Typography>The platform has no fees, subscriptions or payments, so no refund policy applies.</Typography>
      </Block>
      <Block title="7. Changes and contact">
        <Typography>These terms may change as the project develops. The date at the top shows the latest version. Governing law and jurisdiction are set by the institution that operates a deployment.</Typography>
        <Contact />
      </Block>
    </Doc>
  );
}

export function AccessibilityStatement() {
  return (
    <Doc title="Accessibility statement" updated="22 October 2026">
      <Block title="Our aim">
        <Typography>The interface is designed to meet WCAG 2.2 level AA. This prototype has not yet had a formal accessibility audit or testing with a full range of assistive technologies, so the points below describe what the design provides and have not been independently verified.</Typography>
      </Block>
      <Block title="What is in place">
        <Typography component="div">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Everything can be used with a keyboard, and a skip link jumps past the navigation.</li>
            <li>A thick focus outline shows where you are on every control.</li>
            <li>Text and control colours were checked for at least 4.5:1 contrast for text and 3:1 for input borders and focus outlines.</li>
            <li>Status is always written out in words. Colour is never the only signal.</li>
            <li>Every form field has a visible label, and error and confirmation messages are announced to screen readers.</li>
            <li>The layout adapts to phone widths, with a menu button replacing the side navigation.</li>
            <li>Original document pages are shown beside the text read from them, and each page image has a text label.</li>
          </ul>
        </Typography>
      </Block>
      <Block title="Known limits">
        <Typography>
          Scanned paper records are images, so their content is only available as text after it has been read by the document reader and checked by a person. Motion is kept to a minimum: only the grey loading placeholders pulse, and that stops when your device is set to reduce motion.
        </Typography>
      </Block>
      <Block title="Tell us about a problem">
        <Typography>If something is hard to use, please tell us so it can be fixed.</Typography>
        <Contact />
      </Block>
    </Doc>
  );
}
