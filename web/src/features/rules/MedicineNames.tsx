import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
} from "@mui/material";
import { api } from "../../api/client";
import type { MedicineNamesView } from "../../api/types";
import { Empty, ErrorAlert, Loading, PageHeader, Tag } from "../../components/common";

function AddDialog({ view, onClose }: { view: MedicineNamesView; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ display: "", ingredient: "", drug_class: "", kind: "brand" as "brand" | "generic" });
  const add = useMutation({
    mutationFn: () => api.post("/medicine-names", form),
    meta: { success: "Name added. Open referrals were checked again." },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["medicine-names"] });
      onClose();
    },
  });
  const valid = form.display.trim().length >= 2 && form.ingredient.trim().length >= 2 && form.drug_class;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add a medicine name</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <TextField label="Name as written (brand or generic)" value={form.display} onChange={(e) => setForm({ ...form, display: e.target.value })} fullWidth />
          <TextField select label="Kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "brand" | "generic" })}>
            <MenuItem value="brand">Brand</MenuItem>
            <MenuItem value="generic">Generic</MenuItem>
          </TextField>
          <TextField
            label="Ingredient (generic)"
            value={form.ingredient}
            onChange={(e) => setForm({ ...form, ingredient: e.target.value })}
            inputProps={{ list: "ingredient-list" }}
            fullWidth
          />
          <datalist id="ingredient-list">
            {view.ingredients.map((i) => (
              <option key={i} value={i} />
            ))}
          </datalist>
          <TextField select label="Drug class" value={form.drug_class} onChange={(e) => setForm({ ...form, drug_class: e.target.value })} fullWidth>
            {Object.entries(view.classes).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </TextField>
          <ErrorAlert error={add.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!valid || add.isPending} onClick={() => add.mutate()}>
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function MedicineNames() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const q = useQuery({ queryKey: ["medicine-names"], queryFn: () => api.get<MedicineNamesView>("/medicine-names") });
  const retire = useMutation({
    mutationFn: (id: number) => api.post(`/medicine-names/${id}/retire`),
    meta: { success: "Name retired." },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["medicine-names"] }),
  });
  const rows = useMemo(() => {
    const s = search.trim().toLowerCase();
    const all = q.data?.names ?? [];
    return (s ? all.filter((n) => n.display.toLowerCase().includes(s) || n.ingredient.toLowerCase().includes(s)) : all)
      .slice()
      .sort((a, b) => a.ingredient.localeCompare(b.ingredient) || a.display.localeCompare(b.display));
  }, [q.data, search]);
  const view = q.data;
  return (
    <>
      <PageHeader
        title="Medicine names"
        subtitle="Brand and generic names used in Pakistan, matched to an ingredient and drug class. A name that is not in this list is reported as not recognised; it is never guessed."
        actions={
          view?.can_edit && (
            <Button variant="contained" onClick={() => setAdding(true)}>
              Add a name
            </Button>
          )
        }
      />
      {view && !view.can_edit && <Alert severity="info" sx={{ mb: 2 }}>Only a clinical reviewer can add or retire names.</Alert>}
      <TextField label="Search name or ingredient" value={search} onChange={(e) => setSearch(e.target.value)} size="small" sx={{ mb: 2, minWidth: 300 }} />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error || retire.error} />
      {view && rows.length === 0 && <Empty>No matching names.</Empty>}
      {view && rows.length > 0 && (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ingredient</TableCell>
                <TableCell>Name as written</TableCell>
                <TableCell>Kind</TableCell>
                <TableCell>Drug class</TableCell>
                {view.can_edit && (
                  <TableCell>
                    <span className="sr-only">Actions</span>
                  </TableCell>
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((n) => (
                <TableRow key={n.id}>
                  <TableCell>{n.ingredient}</TableCell>
                  <TableCell>{n.display}</TableCell>
                  <TableCell>
                    <Tag tone={n.kind === "generic" ? "neutral" : "info"} label={n.kind === "register_brand" ? "DRAP register" : n.kind} />
                  </TableCell>
                  <TableCell>{view.classes[n.drug_class] ?? n.drug_class}</TableCell>
                  {view.can_edit && (
                    <TableCell>
                      <Button size="small" color="error" onClick={() => retire.mutate(n.id)} disabled={retire.isPending}>
                        Retire
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
      {adding && view && <AddDialog view={view} onClose={() => setAdding(false)} />}
    </>
  );
}
