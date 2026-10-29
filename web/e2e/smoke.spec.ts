import path from "node:path";
import { APIRequestContext, expect, Page, request, test } from "@playwright/test";
import { asUser, closeContexts, PASSWORD, shot } from "./helpers";

// Journeys through the real UI. Run on a fresh seed (scripts/reset-and-seed.ps1 -Force) after onboarding
// (python scripts/onboard_participants.py).
// 1. Spec v4 referral for P1 (Rubina Akhtar): Dr Ali's Clinic -> Aga Khan University Hospital, Dentistry. Device keys,
//    consent in the patient portal, records decrypted on the doctor's device, medicines and flags, approve and sign,
//    staff send, intake, the receiving dentist opens and verifies it, accepts and closes; the patient keeps a copy.
// 2. Test request for P3 (Abdul Rehman Gondal): MRI knee at Aga Khan radiology, with a report image (unchanged by v4).

// tests run from web/
const SCAN = path.resolve("../seed-data/documents/imaging/synthetic_mri-knee-coronal.png");
const PASSPHRASE = "correct horse battery staple";

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

/** Set up the device key (first time) or unlock it (after a page load), wherever the key panel is shown. */
async function deviceKey(page: Page) {
  const setup = page.getByRole("button", { name: "Set up device key" });
  const unlock = page.getByRole("button", { name: "Unlock" });
  await expect(setup.or(unlock).first()).toBeVisible({ timeout: 30_000 });
  if (await setup.isVisible()) {
    await setup.click();
    await page.getByLabel("Passphrase", { exact: true }).fill(PASSPHRASE);
    await page.getByLabel("Passphrase again").fill(PASSPHRASE);
  } else {
    await unlock.first().click();
    await page.getByLabel("Passphrase", { exact: true }).fill(PASSPHRASE);
  }
  await page.getByRole("button", { name: "Continue" }).click();
  // the dialog closes once the keys are unlocked (the compact panel then disappears where records are shown)
  await expect(page.getByLabel("Passphrase", { exact: true })).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Set up device key" }).or(page.getByRole("button", { name: "Unlock" }))).toHaveCount(0);
}

async function api(user: string): Promise<APIRequestContext> {
  const kc = await request.newContext();
  const tok = await kc.post("http://localhost:8080/realms/referral/protocol/openid-connect/token", {
    form: { grant_type: "password", client_id: "dev-cli", username: user, password: PASSWORD, scope: "openid" },
  });
  const { access_token } = await tok.json();
  return request.newContext({ baseURL: "http://localhost:3000/api/central/", extraHTTPHeaders: { Authorization: `Bearer ${access_token}` } });
}

test("v4 referral: keys, consent in the portal, decrypt, sign, send, the receiver verifies, the patient keeps a copy", async ({ browser }) => {
  test.setTimeout(900_000);
  // The referring doctor's request (the form itself is checked by the test-request journey's screens).
  const drApi = await api("dr.ali");
  const found = await (await drApi.get("patients/search?q=Rubina")).json();
  const created = await (await drApi.post("referrals", { data: {
    kind: "referral", patient_local_id: found[0].local_patient_id, destination_institution: "akuh", destination_department: "dentistry",
    reason: "Recurrent pericoronitis of the lower left third molar; please assess for surgical removal.", urgency: "routine",
    procedure_status: "planned", planned_procedure: "Surgical removal of impacted lower wisdom tooth", procedure_tags: ["oral_surgery", "bleeding_risk"],
    submit: true } })).json();
  const url = `/referrals/${created.id}`;
  const reference: string = created.reference;

  // Device keys: the referring doctor, a dentist at the receiving department (its group key), the patient.
  const dr = await asUser(browser, "dr.ali");
  await go(dr, "/keys");
  await deviceKey(dr);
  const dentist = await asUser(browser, "dr.faisal");
  await go(dentist, "/keys");
  await deviceKey(dentist);
  const patient = await asUser(browser, "rubina.akhtar");
  await patient.getByRole("button", { name: "Profile" }).click();
  await deviceKey(patient);

  // Staff ask for consent; the patient agrees in the portal (signed on the phone); staff request the records.
  const staff = await asUser(browser, "staff.ali");
  await go(staff, `${url}?tab=records`);
  await staff.getByRole("button", { name: "Ask the patient for consent" }).click();
  await expect(staff.getByText("Waiting for the patient").first()).toBeVisible({ timeout: 30_000 });
  await patient.getByRole("button", { name: "Permissions" }).click();
  await patient.getByRole("button", { name: new RegExp(reference) }).first().click();
  await patient.getByRole("button", { name: "Agree and sign" }).click();
  await expect(patient.getByText(/agreed|Agreed|granted/).first()).toBeVisible({ timeout: 30_000 });
  await go(staff, `${url}?tab=records`);
  await staff.getByRole("button", { name: "Request records" }).click();
  await expect(staff.getByTestId("outcome-drali")).toContainText(/Records received/, { timeout: 60_000 });
  await expect(staff.getByText("Type 2 diabetes mellitus")).toHaveCount(0); // staff: titles only (T-STAFF-1)
  await shot(staff, "v4-staff-titles-only");

  // The doctor decrypts the records on the device, enters the medicines, signs.
  await go(dr, `${url}?tab=records`);
  await deviceKey(dr);
  await expect(dr.getByText(/Type 2 diabetes mellitus/).first()).toBeVisible({ timeout: 60_000 });
  await shot(dr, "v4-doctor-records-decrypted");
  await dr.getByRole("tab", { name: /Medicines/ }).click();
  await dr.getByLabel("Medicine 1").fill("Disprin 75mg");
  await dr.getByRole("button", { name: "Add a medicine" }).click();
  await dr.getByLabel("Medicine 2").fill("Plavix 75 mg");
  await expect(dr.getByTestId("flag").filter({ hasText: /aspirin with clopidogrel|clopidogrel with aspirin/ })).toBeVisible({ timeout: 30_000 });
  await dr.getByTestId("flag").first().getByRole("button", { name: "Ignore" }).click();
  await dr.getByRole("button", { name: "Save the list" }).click();
  await expect(dr.getByText(/Saved, encrypted on this device/)).toBeVisible({ timeout: 30_000 });
  await shot(dr, "v4-doctor-medicines-flags");
  await dr.getByRole("tab", { name: /Approve & sign/ }).click();
  await expect(dr.getByTestId("recipient-key")).toContainText(/department key/, { timeout: 30_000 });
  await dr.getByLabel("Notes for the specialist (optional)").fill("Three episodes since July; on aspirin and clopidogrel.");
  await dr.getByRole("button", { name: /^Approve and sign/ }).click();
  await expect(dr.getByTestId("version-1")).toBeVisible({ timeout: 60_000 });
  await shot(dr, "v4-doctor-signed");

  // Staff send; the receiving staff take it in (titles only) and assign the dentist.
  await go(staff, `${url}?tab=send`);
  await staff.getByRole("button", { name: "Send to Aga Khan University Hospital" }).click();
  await expect(staff.getByText("Sent", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  const aku = await asUser(browser, "staff.aku");
  await go(aku, "/incoming");
  await expect(async () => {
    await aku.reload();
    await aku.getByRole("link", { name: reference }).click({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });
  await aku.getByRole("button", { name: "Acknowledge receipt" }).click();
  // on a fresh seed Rubina is new at Aga Khan; on a re-run she is already linked there
  await expect(aku.getByRole("button", { name: "Confirm the patient" }).or(aku.getByRole("combobox", { name: /^Assign to doctor/ })).first())
    .toBeVisible({ timeout: 30_000 });
  if (await aku.getByRole("button", { name: "Confirm the patient" }).isVisible()) {
    await registerNew(aku, "New patient; CNIC and date of birth checked");
  }
  await choose(aku, "Assign to doctor", /Faisal/);
  await aku.getByRole("button", { name: "Assign", exact: true }).click();
  await expect(aku.getByText("Type 2 diabetes mellitus")).toHaveCount(0);

  // The dentist opens it on the device with the department key, checks the signature, accepts and closes.
  await go(dentist, "/incoming");
  await dentist.getByRole("link", { name: reference }).click();
  await deviceKey(dentist);
  await expect(dentist.getByTestId("package-verification")).toContainText(/every item matches the signature/, { timeout: 60_000 });
  await expect(dentist.getByText(/Type 2 diabetes mellitus/).first()).toBeVisible();
  await shot(dentist, "v4-receiver-verified");
  await dentist.getByRole("button", { name: "Accept referral" }).click();
  await dentist.getByRole("button", { name: "Close referral" }).click();
  await expect(dentist.getByText(/Closed by/)).toBeVisible({ timeout: 30_000 });

  // The patient saves a copy on the phone and opens it: it verifies against the doctor's signature.
  await go(patient, "/");
  await patient.getByRole("button", { name: "Referrals", exact: true }).last().click();
  await patient.getByRole("button", { name: /Dentistry.*Aga Khan University Hospital/ }).first().click();
  await deviceKey(patient);
  await patient.getByRole("button", { name: /Save (a|the latest) copy/ }).click();
  await patient.getByRole("button", { name: "Open my copy" }).click();
  await expect(patient.getByTestId("my-copy")).toContainText(/every item matches the signature/, { timeout: 60_000 });
  await shot(patient, "v4-patient-copy");
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
