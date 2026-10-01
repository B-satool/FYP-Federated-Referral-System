import { Browser, BrowserContext, Page, expect } from "@playwright/test";

export const PASSWORD = process.env.DEMO_USER_PASSWORD ?? "demo1234";
const contexts: BrowserContext[] = [];

/** Sign in through the real Keycloak login page (authorization code + PKCE). */
export async function login(page: Page, username: string) {
  // Retry until the Keycloak login form appears (cold starts can drop the first redirect).
  await expect(async () => {
    await page.goto("/");
    await page.getByRole("button", { name: /sign in with your institution account/i }).click({ timeout: 10_000 });
    await expect(page.locator("#username")).toBeVisible({ timeout: 15_000 });
  }).toPass({ timeout: 120_000 });
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#kc-login").click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

/** A separate browser context (own session) per user, closed by closeContexts(). */
export async function asUser(browser: Browser, username: string): Promise<Page> {
  const ctx = await browser.newContext();
  contexts.push(ctx);
  const page = await ctx.newPage();
  await login(page, username);
  return page;
}

export async function closeContexts() {
  while (contexts.length) await contexts.pop()!.close();
}

export async function shot(page: Page, name: string) {
  await page.screenshot({ path: `../docs/screenshots/${name}.png`, fullPage: true });
}
