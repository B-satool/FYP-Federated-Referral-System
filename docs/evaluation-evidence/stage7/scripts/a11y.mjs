// Stage 7 keyboard + axe checks: node a11y.mjs <web-dir> <out-dir>
import { createRequire } from "module";
import path from "path";
import fs from "fs";
const [webDir, outDir] = process.argv.slice(2);
const req = createRequire(path.join(webDir, "package.json"));
const { chromium } = req("@playwright/test");
const AxeBuilder = req("@axe-core/playwright").default;
const BASE = "http://localhost:3000", PW = process.env.DEMO_USER_PASSWORD;
const out = { keyboard: [], axe: {} };
const log = (id, ok, note) => { out.keyboard.push({ id, ok, note }); console.log(`[${id}] ${ok ? "PASS" : "FAIL"} :: ${note}`); };

async function focusInfo(page) {
  return page.evaluate(() => {
    const el = document.activeElement; if (!el) return null;
    const cs = getComputedStyle(el);
    return { tag: el.tagName, text: (el.innerText || el.getAttribute("aria-label") || el.value || "").trim().slice(0, 50),
             role: el.getAttribute("role"), outline: `${cs.outlineStyle} ${cs.outlineWidth}`, boxShadow: cs.boxShadow !== "none" };
  });
}
async function tabUntil(page, pred, max = 60) {
  for (let i = 0; i < max; i++) { await page.keyboard.press("Tab"); const f = await focusInfo(page); if (f && pred(f)) return { f, presses: i + 1 }; }
  return null;
}
async function axe(page, name) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  out.axe[name] = r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help }));
  console.log(`[axe] ${name}: ${r.violations.length} rule(s) violated: ${r.violations.map((v) => `${v.id}(${v.impact},${v.nodes.length})`).join(", ") || "none"}`);
}

const browser = await chromium.launch({ channel: "chromium" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
try {
  // K1 keyboard-only sign-in
  await page.goto(BASE + "/"); await page.waitForTimeout(1500);
  await axe(page, "sign-in page");
  let hit = await tabUntil(page, (f) => /sign in/i.test(f.text));
  log("K1a reach Sign in by Tab", !!hit, hit ? `${hit.presses} Tab presses; focus outline=${hit.f.outline} shadow=${hit.f.boxShadow}` : "not reached");
  await page.keyboard.press("Enter");
  await page.locator("#username").waitFor({ timeout: 30000 }); await page.waitForLoadState("networkidle");
  const auto = await page.evaluate(() => document.activeElement?.id);
  log("K1b Keycloak username field autofocused", auto === "username", `active element id on load: ${auto}`);
  if (auto !== "username") { const h = await tabUntil(page, (f) => f.tag === "INPUT", 10); console.log("     tabbed to first input in", h && h.presses, "presses"); }
  await page.keyboard.type("dr.malik"); await page.keyboard.press("Tab"); await page.keyboard.type(PW); await page.keyboard.press("Enter");
  const signedIn = await page.getByRole("button", { name: "Sign out" }).waitFor({ timeout: 60000 }).then(() => true).catch(() => false);
  log("K1c Keycloak login completed by keyboard only (Tab, type, Enter)", signedIn, signedIn ? "signed in" : `failed; url=${page.url()}`);
  if (!signedIn) { await page.screenshot({ path: path.join(outDir, "A11Y-login-failure.png") }); throw new Error("keyboard login failed; aborting so later checks are not run signed-out"); }
  // K2 skip link
  await page.goto(BASE + "/referrals"); await page.waitForTimeout(2000);
  await page.keyboard.press("Tab");
  let f = await focusInfo(page);
  log("K2a first Tab reaches skip link", /skip/i.test(f?.text || ""), `first focus: ${JSON.stringify(f)}`);
  await page.keyboard.press("Enter"); await page.waitForTimeout(300);
  const inMain = await page.evaluate(() => !!document.activeElement?.closest("main") || document.activeElement?.id === "main" || location.hash === "#main");
  log("K2b skip link moves focus to main", inMain, `active=${await page.evaluate(() => document.activeElement?.tagName + "#" + document.activeElement?.id)}`);
  await axe(page, "referral list");
  // K3 open a referral by keyboard
  hit = await tabUntil(page, (f) => /REF-2026-00005/.test(f.text), 120);
  log("K3a reach a referral row link by Tab", !!hit, hit ? `${hit.presses} presses, focus=${JSON.stringify(hit.f)}` : "not reached");
  if (hit) { await page.keyboard.press("Enter"); await page.waitForTimeout(2500); }
  log("K3b Enter opens the referral", /referrals\/5/.test(page.url()), page.url());
  await axe(page, "referral workspace (overview)");
  // K4 step tabs operable by keyboard
  hit = await tabUntil(page, (f) => f.role === "tab" && /Medications/.test(f.text), 80);
  log("K4a reach 'Medications & flags' step by Tab", !!hit, hit ? `${hit.presses} presses, outline=${hit.f.outline} shadow=${hit.f.boxShadow}` : "not reached");
  if (hit) { await page.keyboard.press("Enter"); await page.waitForTimeout(2000); }
  const medsShown = await page.getByText(/Medication list|medication flags|Possible medication|Medication mapping/i).first().isVisible().catch(() => false);
  log("K4b Enter activates the step", medsShown, `medications view visible: ${medsShown}`);
  await page.keyboard.press("ArrowRight"); await page.waitForTimeout(800);
  f = await focusInfo(page);
  log("K4c ArrowRight moves between steps (ARIA tabs pattern)", f?.role === "tab" && !/Medications/.test(f.text), `focus after ArrowRight: ${JSON.stringify(f)}`);
  await axe(page, "referral workspace (medications & flags)");
  // K5 dialog: open reason/confirm dialog by keyboard, Escape closes
  await page.goto(BASE + "/referrals/5"); await page.waitForTimeout(2500);
  hit = await tabUntil(page, (f) => /^Cancel referral/i.test(f.text), 120);
  if (hit) {
    await page.keyboard.press("Enter"); await page.waitForTimeout(600);
    const dlg = await page.getByRole("dialog").isVisible().catch(() => false);
    f = await focusInfo(page);
    const focusInDialog = await page.evaluate(() => !!document.activeElement?.closest("[role=dialog]"));
    await page.keyboard.press("Escape"); await page.waitForTimeout(400);
    const closed = !(await page.getByRole("dialog").isVisible().catch(() => false));
    log("K5 dialog opens by Enter, focus moves into it, Escape closes", dlg && focusInDialog && closed, `open=${dlg} focusInside=${focusInDialog} closedByEsc=${closed}`);
  } else log("K5 dialog keyboard", false, "Cancel referral button not reached");
  for (const [name, url] of [["work queue", "/work-queue"], ["patient links", "/patient-links"], ["document review", "/documents/17"]]) {
    await page.goto(BASE + url); await page.waitForTimeout(2500); await axe(page, name);
  }
  await page.goto(BASE + "/referrals/7"); await page.waitForTimeout(2500);
  await page.getByRole("tab", { name: /Brief/ }).first().click(); await page.waitForTimeout(2000); await axe(page, "brief & approval (closed referral)");
  await page.screenshot({ path: path.join(outDir, "A11Y-brief-approval.png"), fullPage: true });
  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } }); const sp = await ctx2.newPage();
  await sp.goto(BASE + "/"); await sp.getByRole("button", { name: /sign in/i }).click(); await sp.locator("#username").fill("dr.ortho"); await sp.locator("#password").fill(PW); await sp.locator("#kc-login").click();
  await sp.getByRole("button", { name: "Sign out" }).waitFor({ timeout: 60000 }); await sp.goto(BASE + "/specialist/cases/1"); await sp.waitForTimeout(2500); await axe(sp, "specialist case");
  // Colour-only: status indicators carry text
  await page.goto(BASE + "/referrals/5"); await page.waitForTimeout(2500);
  await page.getByRole("tab", { name: /Medications/ }).click(); await page.waitForTimeout(2000);
  const flagAlerts = await page.locator("[role=alert]").evaluateAll((els) => els.map((e) => ({ text: e.innerText.slice(0, 60), hasIcon: !!e.querySelector("svg") })));
  log("C1 flag cards carry text + icon (not colour alone)", flagAlerts.length > 0 && flagAlerts.every((a) => a.text.trim() && a.hasIcon), JSON.stringify(flagAlerts.slice(0, 4)));
  await page.screenshot({ path: path.join(outDir, "A11Y-medications-flags.png"), fullPage: true });
} finally {
  fs.writeFileSync(path.join(outDir, "accessibility-results.json"), JSON.stringify(out, null, 1));
  await browser.close();
}
