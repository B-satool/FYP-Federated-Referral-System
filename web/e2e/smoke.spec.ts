import { expect, Page, test } from "@playwright/test";
import { asUser, closeContexts, shot } from "./helpers";

// v2 journey for P5 (Imtiaz Ali Soomro): Dr Ali's Clinic -> Aga Khan University Hospital, General Surgery.
// Run on a fresh seed: scripts/reset-and-seed.ps1 -Force

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

test("doctor requests, staff prepare and send, hospital responds, clinic closes", async ({ browser }) => {
  // 1. The doctor fills in the form.
  const dr = await asUser(browser, "dr.ali");
  await go(dr, "/referrals/new");
  await dr.getByLabel("Find the patient").fill("Imtiaz");
  await dr.getByRole("button", { name: /Imtiaz Ali Soomro/ }).click();
  await choose(dr, "Hospital", "Aga Khan University Hospital");
  await choose(dr, "Department", "General Surgery");
  await dr.getByLabel("Reason for referral").fill("Repeated right upper abdominal pain after fatty meals; gallstones on ultrasound. Please assess for gallbladder removal.");
  await dr.getByLabel("From the list").check();
  await choose(dr, "Procedure", "Laparoscopic cholecystectomy");
  await dr.getByRole("button", { name: "Add a test or scan" }).click();
  await choose(dr, "Type", "Imaging or scan");
  await dr.getByLabel("Test or scan").fill("MRCP");
  await dr.getByLabel("Clinical question").fill("Liver enzymes mildly raised; exclude a common bile duct stone");
  await choose(dr, "Where", /Ziauddin Hospital/);
  await shot(dr, "v2-new-referral");
  await dr.getByRole("button", { name: "Submit request" }).click();
  await dr.waitForURL(/\/referrals\/\d+/);
  const url = new URL(dr.url()).pathname;
  const reference = (await dr.locator("h1").innerText()).split(" · ")[0];

  // 2. Aga Khan staff confirm the patient (new to them).
  const aku = await asUser(browser, "staff.aku");
  await go(aku, "/patient-links");
  await aku.getByRole("button", { name: "Check" }).first().click();
  await aku.getByLabel("How you checked (required)").fill("New patient; CNIC and date of birth checked");
  await shot(aku, "v2-link-check");
  await aku.getByRole("button", { name: "Not registered here: register as a new patient" }).click();
  await expect(aku.getByRole("dialog")).toBeHidden();

  // 3. Clinic staff gather the records and confirm medicines with the patient.
  const staff = await asUser(browser, "staff.ali");
  await go(staff, `${url}?tab=records`);
  await staff.getByRole("button", { name: /Retrieve records/ }).click();
  await expect(staff.getByText("not the most recent").first()).toBeVisible({ timeout: 30_000 });
  await shot(staff, "v2-records");
  await openTab(staff, "Medicines & flags");
  await staff.getByRole("button", { name: "Add a medicine" }).click();
  await staff.getByLabel("Medicine (as the patient says it)").fill("Panadol");
  await staff.getByLabel("Strength").fill("500 mg");
  await staff.getByLabel("How often").fill("as needed");
  await staff.getByRole("button", { name: "Add medicine" }).click();
  await expect(staff.getByRole("cell", { name: /Panadol/ })).toBeVisible();
  await staff.getByRole("button", { name: "I asked the patient about all their medicines" }).click();
  await expect(staff.getByText(/Patient asked about all medicines: /)).toBeVisible();
  await shot(staff, "v2-medicines-staff");

  // 4. The doctor acknowledges the flags.
  await go(dr, `${url}?tab=medicines`);
  await expect(dr.getByText("Medication requires review: antiplatelet agent before surgery").first()).toBeVisible();
  for (let i = 0; i < 10; i++) {
    const btn = dr.getByRole("button", { name: "Acknowledge for this patient" });
    const n = await btn.count();
    if (n === 0) break;
    await btn.first().click();
    await expect(btn).toHaveCount(n - 1, { timeout: 20_000 });
  }
  await shot(dr, "v2-flags-doctor");

  // 5. Staff send; then send the MRCP order.
  await go(staff, `${url}?tab=send`);
  await expect(staff.getByRole("button", { name: "Send to Aga Khan University Hospital" })).toBeEnabled();
  await staff.waitForLoadState("networkidle");
  await shot(staff, "v2-check-and-send");
  await staff.getByRole("button", { name: "Send to Aga Khan University Hospital" }).click();
  await expect(staff.getByText("Sent", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await openTab(staff, "Tests & scans");
  await staff.getByRole("button", { name: "Send to Ziauddin Hospital" }).click();
  await expect(staff.getByText("requested", { exact: true }).first()).toBeVisible({ timeout: 30_000 });

  // 6. Ziauddin radiology accepts and reports.
  const rad = await asUser(browser, "rad.zia");
  await go(rad, "/orders");
  await rad.getByRole("row", { name: /MRCP/ }).getByRole("link").first().click();
  await rad.getByRole("button", { name: "Accept order" }).click();
  await rad.getByLabel("Findings").fill("No common bile duct stone. Multiple gallbladder stones.");
  await rad.getByLabel("Impression").fill("Cholelithiasis without choledocholithiasis.");
  await rad.getByRole("button", { name: "Send report" }).click();
  await expect(rad.getByText("result ready").first()).toBeVisible({ timeout: 30_000 });
  await shot(rad, "v2-order-reported");

  // 7. The Aga Khan surgeon (department inbox) responds.
  const surgeon = await asUser(browser, "dr.naveed");
  await go(surgeon, "/incoming");
  await expect(async () => {
    await surgeon.reload();
    await surgeon.getByRole("link", { name: reference }).click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await surgeon.getByRole("button", { name: "Acknowledge receipt" }).click();
  await surgeon.getByRole("button", { name: "Accept referral" }).click();
  await surgeon.getByLabel("Assessment").fill("Symptomatic gallstones.");
  await surgeon.getByLabel("Plan").fill("Laparoscopic cholecystectomy on the elective list.");
  await surgeon.getByLabel("Instructions for the referring clinic").fill("Cardiology input on antiplatelets before surgery.");
  await shot(surgeon, "v2-incoming-case");
  await surgeon.getByRole("button", { name: "Send response to the referring clinic" }).click();
  await expect(surgeon.getByRole("button", { name: "Send response to the referring clinic" })).toHaveCount(0, { timeout: 30_000 });

  // 8. Doctor reviews; staff inform the patient and close.
  await go(dr, `${url}?tab=response`);
  await expect(async () => {
    await dr.reload();
    await dr.getByRole("button", { name: "I have reviewed the outcome" }).click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await expect(dr.getByText(/Seen by/)).toBeVisible();
  await go(staff, `${url}?tab=response`);
  await staff.getByRole("button", { name: "Record that the patient was told" }).click();
  await staff.getByLabel("How and what (e.g. phoned, clinic date given)").fill("Phoned the patient; surgical clinic date given");
  await staff.getByRole("button", { name: "Record", exact: true }).click();
  await staff.getByRole("button", { name: "Close referral" }).click();
  await expect(staff.getByText(/Closed by/)).toBeVisible();
  await shot(staff, "v2-closed");
});
