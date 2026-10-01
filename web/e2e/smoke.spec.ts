import { expect, Page, test } from "@playwright/test";
import path from "node:path";
import { asUser, closeContexts, shot } from "./helpers";

test.afterEach(async () => {
  await closeContexts();
});

const SAMPLES = path.resolve(process.cwd(), "../samples/documents");

/** Navigate, retrying transient connection resets from the local Docker port proxy. */
async function go(page: Page, url: string) {
  await expect(async () => {
    await page.goto(url);
  }).toPass({ timeout: 60_000 });
}

async function uploadFile(page: Page, file: string) {
  await page.locator('input[type="file"]').setInputFiles(path.join(SAMPLES, file));
  const btn = page.getByRole("button", { name: "Upload", exact: true });
  await expect(btn).toBeEnabled();
  await btn.click();
}

async function chooseOption(page: Page, label: string, option: string) {
  await page.getByLabel(label).click();
  await page.getByRole("option", { name: option, exact: true }).click();
  await expect(page.getByRole("listbox")).toHaveCount(0);
}

async function approveAllRules(page: Page) {
  await go(page, "/rules");
  await expect(page.getByRole("heading", { name: /Medication rules/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  for (let i = 0; i < 10; i++) {
    const buttons = page.getByRole("button", { name: "Approve and activate" });
    if ((await buttons.count()) === 0) break;
    await buttons.first().click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.waitForLoadState("networkidle");
  }
  await shot(page, "rules-review");
}

async function createReferral(page: Page, patient: string, procedureLabel: string | null): Promise<string> {
  await go(page, "/referrals/new");
  await page.getByRole("button", { name: new RegExp(patient) }).first().click();
  await page.getByLabel("Reason for referral").fill("Crowding of lower incisors and jaw discomfort; orthodontic opinion requested");
  if (procedureLabel) {
    await page.getByLabel("Known", { exact: true }).check();
    await page.getByLabel("Procedure", { exact: true }).click();
    await page.getByRole("option", { name: procedureLabel }).click();
  } else {
    await page.getByLabel("Explicitly unknown", { exact: true }).check();
  }
  await page.getByRole("button", { name: "Create draft" }).click();
  await page.waitForURL(/\/referrals\/\d+/);
  return page.url();
}

async function openTab(page: Page, name: string) {
  await page.getByRole("tab", { name }).click();
}

async function setAllMedicationUses(page: Page, decide: (text: string) => string) {
  await openTab(page, "Medications & flags");
  const rows = page.locator('table[aria-label="Medication list"] tbody tr');
  await expect(rows.first()).toBeVisible();
  const n = await rows.count();
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    const label = decide((await row.innerText()).toLowerCase());
    await row.getByRole("combobox").click();
    await page.getByRole("option", { name: label, exact: true }).click();
    await expect(page.getByRole("option")).toHaveCount(0);
    await page.waitForLoadState("networkidle");
  }
}

/** Click every enabled button with this name, waiting for the list to refetch between clicks. */
async function clickAllEnabled(page: Page, name: string) {
  await page.waitForLoadState("networkidle");
  for (let i = 0; i < 15; i++) {
    const enabled = page.getByRole("button", { name, exact: true }).and(page.locator(":enabled"));
    const n = await enabled.count();
    if (n === 0) break;
    // Keyboard activation (also exercises keyboard operability, NFR 10.3).
    await enabled.first().focus();
    await page.keyboard.press("Enter");
    await expect(enabled).toHaveCount(n - 1, { timeout: 20_000 }).catch(() => undefined);
    await page.waitForLoadState("networkidle");
  }
}

async function reviewAllFlags(page: Page) {
  await clickAllEnabled(page, "Mark reviewed");
}

async function sendForApprovalAndApprove(page: Page) {
  await openTab(page, "Overview");
  const send = page.getByRole("button", { name: "Send for clinician approval" });
  if (await send.isVisible().catch(() => false)) {
    await send.click();
    await page.waitForLoadState("networkidle");
  }
  await openTab(page, "Brief & approval");
  await page.getByRole("button", { name: "Approve this exact version" }).click();
  await expect(page.getByText(/^v\d+$/).first()).toBeVisible();
  await page.getByRole("button", { name: "Send approved version to specialist" }).click();
}

const ayeshaUse = (t: string) =>
  t.includes("warfarin") || t.includes("atorvastatin") ? "Confirmed current" : t.includes("alendronate") ? "Historical / stopped" : "Uncertain";

test("1. normal end-to-end referral through specialist response and closure", async ({ browser }) => {
  const reviewer = await asUser(browser, "dr.reviewer");
  await approveAllRules(reviewer);

  const staff = await asUser(browser, "staff.a");
  const url = await createReferral(staff, "Ayesha Khan", "Tooth extraction (as part of orthodontic plan)");
  await openTab(staff, "Sources & evidence");
  await staff.getByRole("button", { name: "Retrieve permitted records" }).click();
  await expect(staff.getByText("successful", { exact: true }).first()).toBeVisible();
  await expect(staff.getByText(/No verified patient link/).first()).toBeVisible();
  await shot(staff, "sources-and-evidence");

  // Clinic staff were not permitted the "conditions" category at the clinic source (partial result).
  await expect(staff.getByText(/Categories withheld by source authorization: conditions/).first()).toBeVisible();

  const dr = await asUser(browser, "dr.malik");
  await go(dr, url);
  await openTab(dr, "Sources & evidence");
  await dr.getByRole("button", { name: "Retrieve permitted records" }).click();
  await expect(dr.getByText("Conditions (2)")).toBeVisible();
  await openTab(dr, "Overview");
  await dr.getByRole("button", { name: "Assign me as referring clinician" }).click();
  await expect(dr.getByRole("button", { name: "Assign me as referring clinician" })).toHaveCount(0);
  await dr.waitForLoadState("networkidle");
  await chooseOption(dr, "Priority (clinician-selected)", "routine");
  await dr.getByRole("button", { name: "Save details" }).click();
  await dr.waitForLoadState("networkidle");

  await setAllMedicationUses(dr, ayeshaUse);
  await expect(dr.getByText("Medication requires review: anticoagulant recorded")).toBeVisible();
  await expect(dr.getByText(/Possible medication use/).first()).toBeVisible();
  await reviewAllFlags(dr);
  await shot(dr, "medication-flags");

  await openTab(dr, "Brief & approval");
  await dr.getByRole("button", { name: "Start from evidence template" }).click();
  await expect(dr.getByText("Relevant documented history")).toBeVisible();
  await sendForApprovalAndApprove(dr);
  await shot(dr, "brief-and-approval");
  await expect(dr.getByText("Submitted").first()).toBeVisible({ timeout: 60_000 });

  const spec = await asUser(browser, "dr.ortho");
  const ref = (await dr.locator("h1").innerText()).split(" · ")[0];
  await go(spec, "/specialist");
  await spec.getByRole("link", { name: ref }).click();
  await spec.getByRole("button", { name: "Acknowledge receipt" }).click();
  await expect(spec.getByText(/acknowledged by/)).toBeVisible();
  await clickAllEnabled(spec, "Reviewed");
  await spec.getByRole("button", { name: "Accept referral" }).click();
  await spec.getByLabel("findings").fill("Class II division 1 malocclusion with lower crowding");
  await spec.getByLabel("assessment").fill("Suitable for fixed appliances with lower premolar extractions");
  await spec.getByLabel("recommendations").fill("Coordinate extraction timing with the referring clinic");
  await spec.getByLabel("follow up advice").fill("Referring clinician to confirm anticoagulation plan before extractions");
  await spec.getByRole("button", { name: "Save draft" }).click();
  await spec.getByRole("button", { name: "Approve response" }).click();
  await spec.getByRole("button", { name: "Return to referring clinic" }).click();
  await expect(spec.getByText(/returned/).first()).toBeVisible();
  await shot(spec, "specialist-case");

  await dr.reload();
  await openTab(dr, "Specialist & follow-up");
  await expect(dr.getByRole("button", { name: "Record clinician review" })).toBeVisible({ timeout: 60_000 });
  await dr.getByRole("button", { name: "Record clinician review" }).click();
  await dr.getByLabel("Review note").fill("Plan noted; will liaise with cardiology");
  await dr.getByRole("button", { name: "Record review" }).click();
  await dr.getByLabel("Task (as specified by the clinician)").fill("Liaise with cardiology about peri-extraction anticoagulation");
  await dr.getByLabel("Owner").fill("Hina Raza");
  await dr.getByRole("button", { name: "Add task" }).click();
  await dr.getByRole("button", { name: "Completed", exact: true }).click();
  await dr.getByLabel("Outcome").fill("Cardiology plan received and filed");
  await dr.getByRole("button", { name: "Save" }).click();
  await dr.getByRole("button", { name: "Close referral" }).click();
  await expect(dr.getByText(/closed by/)).toBeVisible();
  await shot(dr, "follow-up-closed");
  await openTab(dr, "Audit trail");
  await expect(dr.getByText("referral.approve").first()).toBeVisible();
  await shot(dr, "audit-trail");
});

test("2. denied source and unreadable document with manual fallback", async ({ browser }) => {
  const staff = await asUser(browser, "staff.a");
  await createReferral(staff, "Fatima Noor", null);
  await openTab(staff, "Sources & evidence");
  await staff.getByRole("button", { name: "Retrieve permitted records" }).click();
  await expect(staff.getByText("denied", { exact: true }).first()).toBeVisible();
  await expect(staff.getByText(/Lab B denied access/)).toBeVisible();
  await openTab(staff, "Documents");
  await uploadFile(staff, "unreadable_scan.png");
  await expect(staff.getByText("unreadable", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await uploadFile(staff, "rejected_not_a_pdf.pdf");
  await expect(staff.getByText(/Upload rejected/)).toBeVisible();
  await staff.getByRole("link", { name: "unreadable_scan.png" }).click();
  await staff.getByRole("button", { name: "Transcribe manually" }).click();
  await staff.getByLabel("medication", { exact: true }).fill("Salbutamol inhaler");
  await staff.getByLabel("dosage text").fill("2 puffs as needed");
  await staff.getByRole("button", { name: "Add field" }).click();
  await expect(staff.getByText(/Salbutamol inhaler/).first()).toBeVisible();
  await shot(staff, "manual-fallback");

  // OCR path with source evidence beside the original page
  await staff.goBack();
  await uploadFile(staff, "referral_note_scan.jpg");
  await expect(staff.getByText("extracted", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await staff.getByRole("link", { name: "referral_note_scan.jpg" }).click();
  await expect(staff.getByText(/Ecosprin/).first()).toBeVisible();
  await expect(staff.getByAltText(/Original document page 1/)).toBeVisible();
  await shot(staff, "document-review");
});

test("3. changed medication flag requires renewed review", async ({ browser }) => {
  const dr = await asUser(browser, "dr.malik");
  await createReferral(dr, "Ayesha Khan", "Tooth extraction (as part of orthodontic plan)");
  await openTab(dr, "Sources & evidence");
  await dr.getByRole("button", { name: "Retrieve permitted records" }).click();
  await expect(dr.getByText("successful", { exact: true }).first()).toBeVisible();
  await dr.getByRole("tab", { name: "Overview" }).click();
  await chooseOption(dr, "Priority (clinician-selected)", "soon");
  await dr.getByRole("button", { name: "Save details" }).click();
  await setAllMedicationUses(dr, ayeshaUse);
  await reviewAllFlags(dr);
  await openTab(dr, "Brief & approval");
  await dr.getByRole("button", { name: "Start from evidence template" }).click();
  await expect(dr.getByText("Relevant documented history")).toBeVisible();
  await sendForApprovalAndApprove(dr);
  await expect(dr.getByText("Submitted").first()).toBeVisible({ timeout: 60_000 });

  // Confirm Ecosprin (aspirin) is current -> new confirmed antiplatelet flag -> amendment
  await setAllMedicationUses(dr, (t) => (t.includes("ecosprin") ? "Confirmed current" : ayeshaUse(t)));
  await expect(dr.getByText(/Clinical content changed after version 1 was submitted/)).toBeVisible();
  await expect(dr.getByText("Medication requires review: antiplatelet agent recorded")).toBeVisible();
  await expect(dr.getByRole("button", { name: "Mark reviewed" }).first()).toBeVisible();
  await shot(dr, "changed-flag-amendment");
  await reviewAllFlags(dr);
  await openTab(dr, "Brief & approval");
  await dr.getByRole("button", { name: "Approve this exact version" }).click();
  await dr.getByRole("button", { name: "Send approved version to specialist" }).click();
  await expect(dr.getByText("delivered v2")).toBeVisible({ timeout: 60_000 });
});
