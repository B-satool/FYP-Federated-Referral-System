import { createRequire } from "module"; import path from "path";
const [webDir, outDir] = process.argv.slice(2);
const { chromium } = createRequire(path.join(webDir, "package.json"))("@playwright/test");
const BASE = "http://localhost:3000", PW = process.env.DEMO_USER_PASSWORD;
const b = await chromium.launch({ channel: "chromium" }); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await p.goto(BASE + "/"); await p.getByRole("button", { name: /sign in/i }).click(); await p.locator("#username").fill("dr.malik"); await p.locator("#password").fill(PW); await p.locator("#kc-login").click();
await p.getByRole("button", { name: "Sign out" }).waitFor({ timeout: 60000 });
await p.goto(BASE + "/referrals/5"); await p.waitForTimeout(3000);
const tabs = await p.locator("[role=tablist] [role=tab]").evaluateAll((els) => els.map((e) => ({ text: e.innerText.replace(/\s+/g, " ").slice(0, 30), tabindex: e.getAttribute("tabindex"), selected: e.getAttribute("aria-selected"), tag: e.tagName, controls: e.getAttribute("aria-controls") })));
console.log("[K4] step tabs:", JSON.stringify(tabs));
let reached = null;
for (let i = 0; i < 120; i++) { await p.keyboard.press("Tab"); const f = await p.evaluate(() => ({ role: document.activeElement?.getAttribute("role"), text: document.activeElement?.innerText?.replace(/\s+/g, " ").slice(0, 30), focusVisible: document.activeElement?.matches(":focus-visible"), outline: getComputedStyle(document.activeElement).outlineStyle })); if (f.role === "tab") { reached = { i: i + 1, ...f }; break; } }
console.log("[K4] first tab reached by Tab:", JSON.stringify(reached));
if (reached) {
  await p.keyboard.press("ArrowRight"); await p.waitForTimeout(500);
  const a = await p.evaluate(() => ({ role: document.activeElement?.getAttribute("role"), text: document.activeElement?.innerText?.replace(/\s+/g, " ").slice(0, 30) }));
  console.log("[K4] after ArrowRight:", JSON.stringify(a));
  for (let i = 0; i < 12; i++) { const t = await p.evaluate(() => document.activeElement?.innerText || ""); if (/Medications/.test(t)) break; await p.keyboard.press("Tab"); }
  const at = await p.evaluate(() => document.activeElement?.innerText?.replace(/\s+/g, " ").slice(0, 30));
  await p.keyboard.press("Enter"); await p.waitForTimeout(1500);
  const sel = await p.locator("[role=tab][aria-selected=true]").innerText().catch(() => "?");
  console.log(`[K4] focused '${at}', pressed Enter -> selected step now '${sel.replace(/\s+/g, " ").slice(0, 40)}'`);
  await p.keyboard.press("Shift+Tab"); await p.keyboard.press("Tab"); await p.screenshot({ path: path.join(outDir, "A11Y-step-tab-keyboard-focus.png"), clip: { x: 260, y: 300, width: 1180, height: 160 } });
}
await p.goto(BASE + "/"); await p.getByRole("button", { name: "Sign out" }).click().catch(() => {}); await p.waitForTimeout(1500);
await p.goto(BASE + "/"); await p.waitForTimeout(1500); await p.keyboard.press("Tab"); await p.keyboard.press("Tab");
console.log("[K1a] sign-in button focus:", JSON.stringify(await p.evaluate(() => ({ text: document.activeElement?.innerText, focusVisible: document.activeElement?.matches(":focus-visible"), cls: document.activeElement?.className.includes("focusVisible"), bg: getComputedStyle(document.activeElement).backgroundColor }))));
await p.screenshot({ path: path.join(outDir, "A11Y-signin-button-keyboard-focus.png") });
await b.close();
