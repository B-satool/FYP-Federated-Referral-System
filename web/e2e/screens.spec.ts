import { expect, test } from "@playwright/test";
import { asUser, closeContexts, login, PASSWORD } from "./helpers";

// Visual review of the redesigned screens (desktop + phone). Writes to ../docs/screenshots/redesign-*.png.
const OUT = "../docs/screenshots/redesign";

test.afterEach(async () => {
  await closeContexts();
});

test("desktop screens", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /sign in with your institution account/i })).toBeVisible();
  await page.screenshot({ path: `${OUT}-signin.png`, fullPage: true });
  await login(page, "dr.malik");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}-workqueue.png`, fullPage: true });
  await page.goto("/referrals");
  await page.getByRole("link", { name: /REF-/ }).first().click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}-workspace-overview.png`, fullPage: true });
  // Viewport-only shot after scrolling: the sticky sidebar must still fill the left edge.
  await page.mouse.wheel(0, 5000);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}-workspace-scrolled.png` });
  await page.getByRole("tab", { name: /Brief/ }).click();
  await expect(page.locator(".MuiSkeleton-root")).toHaveCount(0, { timeout: 30_000 });
  await page.screenshot({ path: `${OUT}-workspace-brief.png`, fullPage: true });
  await page.getByRole("tab", { name: /Medications/ }).click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}-workspace-medications.png`, fullPage: true });
  await page.goto("/does-not-exist");
  await page.screenshot({ path: `${OUT}-404.png`, fullPage: true });
  await page.goto("/privacy");
  await page.screenshot({ path: `${OUT}-privacy.png`, fullPage: true });
});

test("other roles", async ({ browser }) => {
  for (const user of ["staff.a", "lab.b", "dr.ortho", "admin.a"]) {
    const page = await asUser(browser, user);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${OUT}-home-${user}.png`, fullPage: true });
  }
});

test("phone screens", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  // On a phone "Sign out" lives in the closed drawer, so wait for the menu button instead.
  await page.goto("/");
  await page.screenshot({ path: `${OUT}-phone-signin.png`, fullPage: true });
  await page.getByRole("button", { name: /sign in with your institution account/i }).click();
  await page.locator("#username").fill("dr.malik");
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await expect(page.getByRole("button", { name: "Open menu" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}-phone-workqueue.png`, fullPage: true });
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.screenshot({ path: `${OUT}-phone-menu.png` });
  await page.getByRole("button", { name: "Close menu" }).click();
  await page.goto("/referrals");
  await page.getByRole("link", { name: /REF-/ }).first().click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: `${OUT}-phone-workspace.png`, fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log("horizontal overflow px on phone workspace:", overflow);
  await ctx.close();
});
