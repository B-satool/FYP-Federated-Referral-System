import { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Link,
} from "@mui/material";
import Add from "@mui/icons-material/Add";
import { api } from "../../api/client";
import type { Referral } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, PageHeader, ReferralStatus, Tag } from "../../components/common";
import { useRefData } from "../../hooks";

export function ReferralList() {
  const nav = useNavigate();
  const ref = useRefData();
  const [filters, setFilters] = useState({ patient: "", reference: "", status: "", date_from: "", date_to: "" });
  const [applied, setApplied] = useState(filters);
  const params = new URLSearchParams(Object.entries(applied).filter(([, v]) => v) as [string, string][]);
  const q = useQuery({
    queryKey: ["referrals", applied],
    queryFn: () => api.get<Referral[]>(`/referrals?${params.toString()}`),
  });

  return (
    <>
      <PageHeader
        title="Referrals"
        subtitle="Search and filter your institution's referrals"
        actions={
          <Button variant="contained" startIcon={<Add />} onClick={() => nav("/referrals/new")}>
            New referral
          </Button>
        }
      />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack
          component="form"
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          onSubmit={(e) => {
            e.preventDefault();
            setApplied(filters);
          }}
        >
          <TextField size="small" label="Patient name or local ID" value={filters.patient} onChange={(e) => setFilters({ ...filters, patient: e.target.value })} />
          <TextField size="small" label="Referral ID" value={filters.reference} onChange={(e) => setFilters({ ...filters, reference: e.target.value })} />
          <TextField size="small" select label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} sx={{ minWidth: 200 }}>
            <MenuItem value="">Any status</MenuItem>
            {Object.entries(ref.data?.statuses ?? {}).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </TextField>
          <TextField size="small" type="date" label="Created from" InputLabelProps={{ shrink: true }} value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
          <TextField size="small" type="date" label="Created to" InputLabelProps={{ shrink: true }} value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
          <Button type="submit" variant="outlined">
            Search
          </Button>
        </Stack>
      </Paper>
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {q.data && (
        <TableContainer component={Paper}>
          <Table size="small" aria-label="Referrals">
            <TableHead>
              <TableRow>
                <TableCell>Referral</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>Destination</TableCell>
                <TableCell>Priority</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Delivery</TableCell>
                <TableCell>Updated</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/referrals/${r.id}`}>
                      {r.reference}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {r.patient.name}
                    <Typography variant="caption" display="block" color="text.secondary">
                      {r.patient.institution_id} / {r.patient.local_patient_id}
                    </Typography>
                  </TableCell>
                  <TableCell>{r.destination_name}</TableCell>
                  <TableCell>{r.priority ?? <Tag tone="warn" label="not set" />}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <ReferralStatus status={r.status} label={r.status_label} />
                      {r.amendment_open && <Tag tone="warn" label="amendment" />}
                    </Stack>
                  </TableCell>
                  <TableCell>{r.delivery_status === "none" ? "—" : r.delivery_status}</TableCell>
                  <TableCell>{fmtDate(r.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {q.data.length === 0 && <Empty>No referrals match.</Empty>}
        </TableContainer>
      )}
    </>
  );
}
