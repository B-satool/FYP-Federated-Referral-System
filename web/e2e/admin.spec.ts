import { expect, Page, test } from "@playwright/test";
import { asUser, closeContexts, shot } from "./helpers";

// Role templates: an institution administrator changes an account's role on the Accounts screen.
// Run on a fresh seed: scripts/reset-and-seed.ps1 -Force

test.afterEach(async () => {
  await closeContexts();
});

async function setRole(page: Page, username: string, template: string, reason: string) {
  const row = page.getByRole("row", { name: new RegExp(`\\(${username.replace(".", "\\.")}\\)`) });
  await row.getByRole("combobox").click();
  await page.getByRole("option", { name: template }).click();
  await page.getByRole("dialog").getByLabel("Reason").fill(reason);
  await page.getByRole("button", { name: "Change role" }).click();
  await expect(page.getByText(/Role changed/)).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(row.getByRole("combobox")).toContainText(template);
}

test("administrator changes a role with a template; the menu follows on the next sign-in", async ({ browser }) => {
  const admin = await asUser(browser, "admin.ali");
  await admin.getByRole("link", { name: "Accounts and roles" }).click();
  await expect(admin.getByRole("heading", { name: "Accounts" })).toBeVisible();
  // an administrator cannot change their own role: no picker on their own row
  await expect(admin.getByRole("row", { name: /\(admin\.ali\)/ }).getByRole("combobox")).toHaveCount(0);

  await setRole(admin, "tech.ali", "Staff (referral coordinator)", "Moved to the front desk");
  await shot(admin, "v3-admin-role-templates");
  try {
    const tech = await asUser(browser, "tech.ali");
    await expect(tech.getByRole("link", { name: /Work queue/ })).toBeVisible();
    await expect(tech.getByRole("link", { name: "Test and scan orders" })).toHaveCount(0);
  } finally {
    await setRole(admin, "tech.ali", "Laboratory, radiology or ECG staff", "Test finished, back to the lab");
  }
  const tech = await asUser(browser, "tech.ali");
  await expect(tech.getByRole("link", { name: "Test and scan orders" })).toBeVisible();
});
