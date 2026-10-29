import { ReactNode } from "react";
import { Alert, Box, Divider, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import type { BriefSection, BriefStatement, LetterFlag, PackageEnvelope } from "../api/types";
import { tokens } from "../theme";
import { fmtDate } from "./common";

export type LetterHeader = {
  reference: string;
  date: string | null;
  to: { institution: string | null; department: string | null; doctor?: string | null };
  from: { doctor: string; department?: string | null; institution: string };
  patient: { name: string; birth_date: string | null; sex: string | null; cnic?: string | null; id?: string | null };
  urgency: string;
  urgencyDetail?: string | null;
};

const SEX: Record<string, string> = { F: "female", M: "male", U: "not recorded", female: "female", male: "male" };

/** "35102-1234567-1" from "3510212345671" (left unchanged if it is not 13 digits). */
export function fmtCnic(v?: string | null): string {
  if (!v) return "Not recorded";
  const d = v.replace(/\D/g, "");
  return d.length === 13 ? `${d.slice(0, 5)}-${d.slice(5, 12)}-${d.slice(12)}` : v;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="div" sx={{ color: tokens.muted, textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </Typography>
      <Typography variant="body2" component="div" sx={{ overflowWrap: "anywhere" }}>
        {children}
      </Typography>
    </Box>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 700, borderBottom: `1px solid ${tokens.line}`, pb: 0.5, mb: 1 }}>
      {children}
    </Typography>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return (
    <Typography component="span" variant="body2" sx={{ color: tokens.muted }}>
      {children}
    </Typography>
  );
}

type Cite = (ids: number[]) => ReactNode;

function SourceLine({ st, cite }: { st: BriefStatement; cite?: Cite }) {
  const bits = [st.date ? fmtDate(st.date, false) : null, st.source].filter(Boolean).join(" · ");
  if (!bits && !(cite && st.evidence_ids.length)) return null;
  return (
    <>
      {" "}
      <Muted>{bits}</Muted> {cite && cite(st.evidence_ids.slice(0, 4))}
    </>
  );
}

function Paragraphs({ s }: { s: BriefSection }) {
  return (
    <>
      {s.statements.map((st) => (
        <Typography key={st.id} variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
          {st.text}
        </Typography>
      ))}
    </>
  );
}

function Bullets({ s, cite }: { s: BriefSection; cite?: Cite }) {
  return (
    <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
      {s.statements.map((st) => (
        <li key={st.id}>
          <Typography variant="body2" component="span">
            {st.text}
          </Typography>
          <SourceLine st={st} cite={cite} />
        </li>
      ))}
    </Box>
  );
}

function Medicines({ s, cite }: { s: BriefSection; cite?: Cite }) {
  return (
    <Table size="small" aria-label="Current medicines">
      <TableHead>
        <TableRow>
          <TableCell>Medicine and dose</TableCell>
          <TableCell>Recorded at</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {s.statements.map((st) => (
          <TableRow key={st.id}>
            <TableCell>{st.text}</TableCell>
            <TableCell>
              <Muted>{st.source ?? ""}</Muted> {cite && cite(st.evidence_ids.slice(0, 3))}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Results of one panel together (e.g. "Lipid profile"), newest panel first. */
function Investigations({ s, cite }: { s: BriefSection; cite?: Cite }) {
  const groups: { name: string; rows: BriefStatement[] }[] = [];
  for (const st of s.statements) {
    const name = st.group ?? "";
    const g = groups.find((x) => x.name === name);
    if (g) g.rows.push(st);
    else groups.push({ name, rows: [st] });
  }
  return (
    <Table size="small" aria-label="Investigations">
      <TableHead>
        <TableRow>
          <TableCell>Result</TableCell>
          <TableCell sx={{ width: 120 }}>Date</TableCell>
          <TableCell>Where</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {groups.map((g) => [
          g.name && g.rows.length > 1 ? (
            <TableRow key={`g-${g.name}`}>
              <TableCell colSpan={3} sx={{ fontWeight: 700, backgroundColor: tokens.sunken }}>
                {g.name}
              </TableCell>
            </TableRow>
          ) : null,
          ...g.rows.map((st) => (
            <TableRow key={st.id}>
              <TableCell>{st.text}</TableCell>
              <TableCell>{st.date ? fmtDate(st.date, false) : ""}</TableCell>
              <TableCell>
                <Muted>{st.source ?? ""}</Muted> {cite && cite(st.evidence_ids)}
              </TableCell>
            </TableRow>
          )),
        ])}
      </TableBody>
    </Table>
  );
}

const DECISION: Record<string, string> = { reviewed: "Reviewed", ignore: "Ignored as not relevant", research: "Marked for research" };
const MINOR = ["Minor", "Unknown", "low"];

function FlagLine({ f }: { f: LetterFlag }) {
  const source = f.source_type === "manual_rule" ? `Approved rule ${f.source_version ?? f.rule_id ?? ""}`
    : f.source_name ? `${f.source_name}${f.source_version ? `, ${f.source_version}` : ""}${f.auto_generated ? " (automatically generated, not clinically reviewed)" : ""}` : "";
  return (
    <Box sx={{ borderLeft: `3px solid ${f.kind === "confirmed" || f.severity === "Major" || f.severity === "high" ? tokens.warn.text : tokens.field}`, pl: 1.5 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {f.title}
        {f.severity ? ` · ${f.severity === "Unknown" ? "severity not graded" : f.severity.toLowerCase()}` : ""}
      </Typography>
      <Typography variant="body2">{f.message}</Typography>
      {f.source_quote && <Typography variant="body2" sx={{ fontStyle: "italic", color: tokens.muted }}>"{f.source_quote}"</Typography>}
      <Muted>
        {[source, f.acknowledged ? `${DECISION[f.acknowledged.decision ?? "reviewed"]} by ${f.acknowledged.by}, ${fmtDate(f.acknowledged.at)}${f.acknowledged.note ? `: ${f.acknowledged.note}` : ""}` : "No decision recorded"]
          .filter(Boolean).join(" · ")}
      </Muted>
    </Box>
  );
}

function FlagsSection({ flags, summary }: { flags: LetterFlag[]; summary?: string | null }) {
  const main = flags.filter((f) => !MINOR.includes(f.severity ?? ""));
  const minor = flags.filter((f) => MINOR.includes(f.severity ?? ""));
  return (
    <Box>
      <Heading>Medication review</Heading>
      <Typography variant="body2" sx={{ color: tokens.muted, mb: 1 }}>
        From approved rules, the DDInter interaction database and US drug labels, checked against the current medicines, the
        planned procedure and recorded conditions. A decision means the referring doctor has seen the flag; it is not advice to
        change a medicine.
      </Typography>
      {flags.length === 0 && <Typography variant="body2">{summary ?? "No rule or suggestion on file."}</Typography>}
      <Stack spacing={1}>
        {main.map((f) => <FlagLine key={f.flag_id} f={f} />)}
      </Stack>
      {minor.length > 0 && (
        <Box component="details" sx={{ mt: 1 }}>
          <summary>
            <Typography component="span" variant="body2">{minor.length} minor, ungraded or precaution-level flag(s)</Typography>
          </summary>
          <Stack spacing={1} sx={{ mt: 1 }}>
            {minor.map((f) => <FlagLine key={f.flag_id} f={f} />)}
          </Stack>
        </Box>
      )}
    </Box>
  );
}

type LetterAiSuggestion = NonNullable<PackageEnvelope["ai_suggestions"]>[number];

/** Labelled model suggestions, kept apart from the medication review: never flags, never verified. */
function AiSuggestionsSection({ items }: { items: LetterAiSuggestion[] }) {
  return (
    <Box>
      <Heading>AI suggestions (not verified)</Heading>
      <Typography variant="body2" sx={{ color: tokens.muted, mb: 1 }}>
        Possible clashes between current medicines that have no DDInter entry, suggested by a model. AI suggestion, not
        verified. They are not medication flags and are not advice.
      </Typography>
      <Stack spacing={1}>
        {items.map((s) => (
          <Box key={s.pair_key} sx={{ borderLeft: `3px solid ${tokens.field}`, pl: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{s.ingredients.join(" and ")}</Typography>
            <Typography variant="body2">{s.reason}</Typography>
            <Muted>
              {[`Model ${s.model_version}`, s.decision ? `${s.decision.decision === "research" ? "Marked for research" : "Ignored as not relevant"} by ${s.decision.by}` : "No decision recorded"].join(" · ")}
            </Muted>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/**
 * The referral laid out as a letter a practitioner can read top to bottom: who it is to and from,
 * the patient, why, the planned procedure, current medicines, history, investigations, imaging,
 * the medication review and what could not be obtained. Used for "what will be sent", the sent
 * version, and the receiving institution's copy.
 */
export function ReferralLetter({
  header,
  sections,
  flags,
  flagSummary,
  aiSuggestions,
  footer,
  cite,
}: {
  header: LetterHeader;
  sections: BriefSection[];
  flags?: LetterFlag[];
  flagSummary?: string | null;
  aiSuggestions?: LetterAiSuggestion[];
  footer?: ReactNode;
  cite?: Cite;
}) {
  const by = Object.fromEntries(sections.map((s) => [s.key, s]));
  const p = header.patient;
  const body: [string, (s: BriefSection) => ReactNode][] = [
    ["reason", (s) => <Paragraphs s={s} />],
    ["notes", (s) => <Paragraphs s={s} />],
    ["procedure", (s) => <Paragraphs s={s} />],
    ["medications", (s) => <Medicines s={s} cite={cite} />],
    ["conditions", (s) => <Bullets s={s} cite={cite} />],
    ["surgeries", (s) => <Bullets s={s} cite={cite} />],
    ["visits", (s) => <Bullets s={s} cite={cite} />],
    ["results", (s) => <Investigations s={s} cite={cite} />],
    ["imaging", (s) => <Bullets s={s} cite={cite} />],
  ];
  const outstanding = by.outstanding;
  return (
    <Paper variant="outlined" component="article" aria-label={`Referral letter ${header.reference}`} sx={{ p: { xs: 2, md: 3.5 }, maxWidth: 900 }}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 2 }}>
        <Box>
          <Typography variant="overline" sx={{ color: tokens.muted }}>
            Referral letter
          </Typography>
          <Typography variant="h6" component="h2">
            {header.to.department ?? "Referral"}
            {header.to.institution ? `, ${header.to.institution}` : ""}
          </Typography>
        </Box>
        <Box sx={{ textAlign: { sm: "right" } }}>
          <Typography variant="body2">{header.reference}</Typography>
          <Typography variant="body2" sx={{ color: tokens.muted }}>
            {header.date ? fmtDate(header.date, false) : "Not sent yet"}
          </Typography>
        </Box>
      </Stack>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2, mb: 2 }}>
        <Field label="To">
          {header.to.doctor ? `${header.to.doctor}, ` : ""}
          {header.to.department}
          {header.to.institution ? <><br />{header.to.institution}</> : null}
        </Field>
        <Field label="From">
          {header.from.doctor}
          {header.from.department ? `, ${header.from.department}` : ""}
          <br />
          {header.from.institution}
        </Field>
        <Field label="Patient">
          <strong>{p.name}</strong>
          <br />
          Born {p.birth_date ? fmtDate(p.birth_date, false) : "not recorded"}, {SEX[p.sex ?? "U"] ?? p.sex}
          <br />
          CNIC {fmtCnic(p.cnic)}
          {p.id ? <><br />Our record: {p.id}</> : null}
        </Field>
        <Field label="Urgency">
          <strong>{header.urgency}</strong>
          {header.urgencyDetail ? <><br />{header.urgencyDetail}</> : null}
        </Field>
      </Box>
      <Divider sx={{ mb: 2 }} />
      <Stack spacing={2.5}>
        {body.map(([key, render]) =>
          by[key] ? (
            <Box key={key} component="section">
              <Heading>{by[key].title}</Heading>
              {render(by[key])}
            </Box>
          ) : null,
        )}
        {flags && <FlagsSection flags={flags} summary={flagSummary} />}
        {aiSuggestions && aiSuggestions.length > 0 && <AiSuggestionsSection items={aiSuggestions} />}
        {outstanding && (
          <Alert severity="warning" variant="outlined">
            <Typography variant="subtitle2" component="h3">
              {outstanding.title}
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {outstanding.statements.map((st) => (
                <li key={st.id}>
                  <Typography variant="body2">{st.text}</Typography>
                </li>
              ))}
            </Box>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              Missing information is not a negative finding.
            </Typography>
          </Alert>
        )}
      </Stack>
      {footer && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="body2" component="div" sx={{ color: tokens.muted }}>
            {footer}
          </Typography>
        </>
      )}
    </Paper>
  );
}
