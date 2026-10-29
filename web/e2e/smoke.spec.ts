import path from "node:path";
import { expect, Page, test } from "@playwright/test";
import { asUser, closeContexts, shot } from "./helpers";

// v2 journeys. Run on a fresh seed: scripts/reset-and-seed.ps1 -Force
// 1. Referral for P5 (Imtiaz Ali Soomro): Dr Ali's Clinic -> Aga Khan University Hospital, General Surgery.
// 2. Test request for P3 (Abdul Rehman Gondal): MRI knee at Aga Khan radiology, with a report image.

// tests run from web/
const SCAN = path.resolve("../seed-data/documents/imaging/synthetic_mri-knee-coronal.png");

test.afterEach(async () => {
  await closeContexts();
});

async function go(page: Page, url: string) {
  await expect(async () => {
    await page.goto(url);
  }).toPass({ timeout: 60_000 });
}

async function choose(page: Page, label: string, option: string | RegExp, nth = 0) {
  // A select's accessible name is its label (plus " *" when required, plus the chosen value).
  await page.getByRole("combobox", { name: new RegExp(`^${label}\\b`) }).nth(nth).click();
  await page.getByRole("option", { name: option }).first().click();
  await expect(page.getByRole("listbox")).toHaveCount(0);
}

async function openTab(page: Page, name: string) {
  await page.getByRole("tab", { name: new RegExp(name) }).click();
  await page.waitForLoadState("networkidle");
}

async function pickPatient(page: Page, name: string) {
  await page.getByLabel("Find the patient").fill(name);
  await page.getByRole("button", { name: new RegExp(name) }).first().click();
}

/** Staff at the receiving side confirm who the patient is (new to them). */
async function registerNew(page: Page, note: string) {
  await page.getByRole("button", { name: "Confirm the patient" }).click();
  await page.getByLabel("How you checked (required)").fill(note);
  await page.getByRole("button", { name: "Register as a new patient" }).click();
  await expect(page.getByText(/Patient confirmed/).first()).toBeVisible({ timeout: 30_000 });
}

test("referral: doctor requests, staff prepare, doctor reviews flags, staff send, hospital takes it in and responds", async ({ browser }) => {
  // 1. The doctor chooses what they need, then fills in the referral.
  const dr = await asUser(browser, "dr.ali");
  await go(dr, "/referrals/new");
  await dr.getByRole("button", { name: /Refer to a doctor or department/ }).click();
  await pickPatient(dr, "Imtiaz");
  await choose(dr, "Clinic or hospital", "Aga Khan University Hospital");
  await choose(dr, "Department", "General Surgery");
  await dr.getByLabel("Reason for referral").fill("Repeated right upper abdominal pain after fatty meals; gallstones on ultrasound. Please assess for gallbladder removal.");
  await dr.getByLabel("A procedure is planned").check();
  await dr.getByRole("textbox", { name: /^Procedure/ }).fill("Laparoscopic cholecystectomy");
  await expect(dr.getByLabel(/Major or elective surgery/)).toBeChecked();
  await shot(dr, "v2-new-referral");
  await dr.getByRole("button", { name: "Submit request" }).click();
  await dr.waitForURL(/\/referrals\/\d+/);
  const url = new URL(dr.url()).pathname;
  const reference = (await dr.locator("h1").innerText()).split(" · ")[0];
  await expect(dr.getByText("In progress").first()).toBeVisible();
  await openTab(dr, "Medicines & flags");
  await expect(dr.getByText(/Staff are still retrieving/)).toBeVisible();

  // 2. Clinic staff retrieve the records and mark it ready for the doctor. They see titles, not content.
  const staff = await asUser(browser, "staff.ali");
  await go(staff, `${url}?tab=records`);
  await staff.getByRole("button", { name: /Retrieve records/ }).click();
  await expect(staff.getByRole("cell", { name: "Ziauddin Hospital" })).toBeVisible({ timeout: 30_000 });
  await expect(staff.getByText("retrieved", { exact: true }).first()).toBeVisible();
  await expect(staff.getByText(/You see each record's title only/)).toBeVisible();
  await shot(staff, "v2-records");
  await openTab(staff, "Medicines & flags");
  await expect(staff.getByText(/You see the progress only/)).toBeVisible();
  await expect(staff.getByRole("button", { name: "Add a medicine" })).toHaveCount(0);
  await openTab(staff, "Check & send");
  await staff.getByRole("button", { name: "Ready for the doctor's review" }).click();
  await expect(staff.getByText(/Marked ready by/)).toBeVisible({ timeout: 30_000 });

  // 3. The doctor adds what the patient reports, confirms the medicines, decides on each flag, then marks the packet reviewed.
  await go(dr, `${url}?tab=medicines`);
  await expect(dr.getByText("Medication requires review: antiplatelet agent before surgery").first()).toBeVisible();
  await dr.getByRole("button", { name: "Add a medicine" }).click();
  await dr.getByLabel("Medicine (as the patient says it)").fill("Panadol");
  await dr.getByLabel("Strength").fill("500 mg");
  await dr.getByLabel("How often").fill("as needed");
  await dr.getByRole("button", { name: "Add medicine" }).click();
  await expect(dr.getByRole("cell", { name: /Panadol/ })).toBeVisible();
  await dr.getByRole("button", { name: "I asked the patient about all their medicines" }).click();
  await expect(dr.getByText(/Patient asked about all medicines: /)).toBeVisible();
  await expect(dr.getByText(/Automatically generated, not clinically reviewed/).first()).toBeVisible();
  const needed = dr.getByRole("region", { name: "Needs your decision" });
  await needed.getByRole("button", { name: "Ignore" }).first().click();
  await dr.getByRole("dialog").getByLabel("Note (optional)").fill("Cardiology aware");
  await dr.getByRole("dialog").getByRole("button", { name: "Ignore" }).click();
  await expect(dr.getByText(/Ignored \(not relevant for this patient\) by Dr Ali Raza/)).toBeVisible({ timeout: 20_000 });
  for (let i = 0; i < 15; i++) {
    const btn = needed.getByRole("button", { name: "Mark as reviewed" });
    const n = await btn.count();
    if (n === 0) break;
    await btn.first().click();
    await expect(btn).toHaveCount(n - 1, { timeout: 20_000 });
  }
  await shot(dr, "v2-flags-doctor");
  await openTab(dr, "Referral letter");
  await expect(dr.getByRole("article", { name: /Referral letter/ })).toBeVisible();
  await dr.getByRole("button", { name: "Mark the packet reviewed" }).click();
  await expect(dr.getByText(/Packet reviewed by Dr Ali Raza/)).toBeVisible({ timeout: 20_000 });

  // 4. Staff send it without seeing the letter (staff cannot withdraw a request).
  await go(staff, `${url}?tab=send`);
  await expect(staff.getByRole("button", { name: "Send to Aga Khan University Hospital" })).toBeEnabled({ timeout: 30_000 });
  await expect(staff.getByText(/visible to doctors only/).first()).toBeVisible();
  await staff.waitForLoadState("networkidle");
  await shot(staff, "v2-check-and-send");
  await staff.getByRole("button", { name: "Send to Aga Khan University Hospital" }).click();
  await expect(staff.getByText("Sent", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await openTab(staff, "Request");
  await expect(staff.getByRole("button", { name: "Withdraw request" })).toHaveCount(0);

  // 5. Aga Khan staff take it in: acknowledge, confirm the patient (new to them), assign the surgeon.
  const aku = await asUser(browser, "staff.aku");
  await go(aku, "/incoming");
  await expect(async () => {
    await aku.reload();
    await aku.getByRole("link", { name: reference }).click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await aku.getByRole("button", { name: "Acknowledge receipt" }).click();
  await registerNew(aku, "New patient; CNIC and date of birth checked");
  await choose(aku, "Assign to doctor", "Dr Naveed Baig");
  await aku.getByRole("button", { name: "Assign", exact: true }).click();
  await expect(aku.getByText(/Dr Naveed Baig/).first()).toBeVisible();
  await shot(aku, "v2-incoming-intake");

  // 6. The surgeon accepts (no response to write) and later marks it complete.
  const surgeon = await asUser(browser, "dr.naveed");
  await go(surgeon, "/incoming");
  await surgeon.getByRole("link", { name: reference }).click();
  await surgeon.getByRole("button", { name: "Accept referral" }).click();
  await expect(surgeon.getByText(/Kept until/)).toBeVisible({ timeout: 15_000 });
  await expect(surgeon.getByLabel("Assessment")).toHaveCount(0);
  await shot(surgeon, "v2-incoming-case");
  await surgeon.getByRole("button", { name: "Mark as complete" }).click();
  await expect(surgeon.getByText(/Marked complete by Dr Naveed Baig/)).toBeVisible({ timeout: 30_000 });
  await shot(surgeon, "v3-receiver-marked-complete");

  // 7. The clinic is told it was accepted; staff tell the patient; the doctor closes it.
  await go(staff, `${url}?tab=response`);
  await expect(async () => {
    await staff.reload();
    await staff.getByRole("button", { name: "Record that the patient was told" }).click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await staff.getByLabel("How and what (e.g. phoned, clinic date given)").fill("Phoned the patient; surgical clinic date given");
  await staff.getByRole("button", { name: "Record", exact: true }).click();
  await expect(staff.getByText(/Patient informed by/)).toBeVisible();
  await go(dr, `${url}?tab=response`);
  await expect(dr.getByText(/Accepted by Aga Khan University Hospital/)).toBeVisible();
  await expect(dr.getByText(/Marked complete by Dr Naveed Baig/).first()).toBeVisible();
  await dr.getByRole("button", { name: "Close referral" }).click();
  await expect(dr.getByText(/Closed by Dr Ali Raza/)).toBeVisible();
  await shot(dr, "v2-closed");
});

test("test request: MRI at Aga Khan radiology with images, result back to the doctor", async ({ browser }) => {
  const dr = await asUser(browser, "dr.ali");
  await go(dr, "/referrals/new");
  await dr.getByRole("button", { name: /Request a test or scan/ }).click();
  await pickPatient(dr, "Gondal");
  await choose(dr, "Type", "Imaging or scan");
  await dr.getByLabel("Test or scan").fill("MRI knee");
  await dr.getByLabel("Body area").fill("Right knee");
  await dr.getByLabel("Clinical question").fill("Worsening knee pain; assess cartilage and menisci");
  await choose(dr, "Where", /Aga Khan University Hospital/);
  await shot(dr, "v2-new-test-request");
  await dr.getByRole("button", { name: "Submit request" }).click();
  await dr.waitForURL(/\/referrals\/\d+/);
  const url = new URL(dr.url()).pathname;

  // Staff send the order.
  const staff = await asUser(browser, "staff.ali");
  await go(staff, `${url}?tab=tests`);
  await staff.getByRole("button", { name: "Send to Aga Khan University Hospital" }).click();
  await expect(staff.getByText("requested", { exact: true }).first()).toBeVisible({ timeout: 30_000 });

  // Radiology confirms the patient, accepts, and reports with an image.
  const rad = await asUser(browser, "rad.aku");
  await go(rad, "/orders");
  await expect(async () => {
    await rad.reload();
    await rad.getByRole("row", { name: /MRI knee/ }).getByRole("link").first().click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await registerNew(rad, "New patient; CNIC checked at the desk");
  await rad.getByRole("button", { name: "Accept order" }).click();
  await rad.getByLabel("Findings").fill("Medial compartment cartilage thinning; degenerate tear of the medial meniscus.");
  await rad.getByLabel("Impression").fill("Medial compartment osteoarthritis.");
  await rad.getByLabel("Add images or files").setInputFiles(SCAN);
  await rad.getByRole("button", { name: "Send report" }).click();
  await expect(rad.getByRole("article", { name: /Report/ })).toBeVisible({ timeout: 30_000 });
  await shot(rad, "v2-order-reported");

  // The doctor sees the report with the image.
  await go(dr, `${url}?tab=tests`);
  await expect(async () => {
    await dr.reload();
    await expect(dr.getByRole("img", { name: /synthetic_mri-knee-coronal/ })).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await shot(dr, "v2-test-result-doctor");
  await dr.getByRole("button", { name: "I have seen the result" }).click();

  // Staff tell the patient and close.
  await go(staff, `${url}?tab=tests`);
  await staff.getByRole("button", { name: "Record that the patient was told" }).click();
  await staff.getByLabel("How and what (e.g. phoned, clinic date given)").fill("Phoned the patient with the MRI result");
  await staff.getByRole("button", { name: "Record", exact: true }).click();
  await staff.getByRole("button", { name: "Close request" }).click();
  await expect(staff.getByText(/Closed by/)).toBeVisible();
});
