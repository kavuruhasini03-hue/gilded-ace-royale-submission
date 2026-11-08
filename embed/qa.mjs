import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const base = process.env.QA_ORIGIN || "http://localhost:3000";
const output = new URL("../docs/screens/", import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1536, height: 1024 }, colorScheme: "dark" });
const page = await context.newPage();
const privateRun = process.env.QA_PRIVATE === "1";
if (privateRun) {
  const session = await context.newCDPSession(page);
  await session.send("Network.setCookieControls", {
    enableThirdPartyCookieRestriction: true,
    disableThirdPartyCookieMetadata: true,
    disableThirdPartyCookieHeuristics: true,
  });
}
const capture = (name) => page.screenshot({ path: new URL(name + ".png", output).pathname, fullPage: true });
try {
  const [, token] = await Promise.all([
    page.goto(base, { timeout: 20000 }),
    page.waitForResponse((response) => new URL(response.url()).pathname === "/api/token", { timeout: 20000 }),
  ]);
  if (!token.ok()) {
    await page.getByRole("status").filter({ hasText: /could not issue|not configured/ }).waitFor();
    throw new Error("Local shell loaded, but the Databricks token exchange blocked the iframe.");
  }

  page.setDefaultTimeout(12000);
  const frame = page.frameLocator("#dashboard iframe");
  const pages = ["Pit Boss", "Luck Funnel", "Floor Radar", "High-Roller Ladder", "Cashier’s Cage", "Model Room", "Evidence Vault"];
  const headings = ["Theo captured", "M-1158 warrants a payout check", "Bank positions reveal local clusters",
    "The top tenth generated two-thirds of tracked theo", "The July slip funds $1,200",
    "The weekday model cuts holdout MAE by 77%", "Every recommendation has an evidence trail"];

  async function open(name) {
    await frame.getByText(name, { exact: true }).first().click();
    await frame.getByText(headings[pages.indexOf(name)], { exact: true }).first().waitFor();
  }

  async function filter(label, value) {
    const control = frame.getByRole("button", { name: label, exact: true }).or(frame.getByRole("combobox", { name: label, exact: true }));
    await control.first().click();
    await frame.getByText(value, { exact: true }).last().click();
    await page.keyboard.press("Escape");
  }

  if (privateRun) {
    await open("Pit Boss");
    await frame.getByText(/\$248(?:\.9+)?M|248,?905,?/).first().waitFor();
    await capture("06-private-third-party-cookies-blocked");
    console.log("Pit Boss rendered in a fresh context with third-party cookies blocked.");
    await browser.close();
    process.exit(0);
  }

  for (const [index, name] of pages.entries()) {
    await open(name);
    await capture(`page-${index + 1}-${name.toLowerCase().replace(/[^a-z]+/g, "-")}`);
  }

  await open("Pit Boss");
  await frame.getByRole("button", { name: /gaming dates/i }).click();
  await frame.getByRole("textbox", { name: /start/i }).fill("04/01/2025");
  await frame.getByRole("textbox", { name: /end/i }).fill("06/30/2025");
  await frame.getByRole("button", { name: /apply/i }).click();
  await frame.getByText(/124(?:\.0+)?M|124,?003,?503/).first().waitFor();
  await capture("01-date-filter");
  await filter("Bank", "Hotel Corridor · Bank 40");
  await capture("02-bank-filter");

  await open("High-Roller Ladder");
  await filter("Tier", "Gold");
  await capture("03-tier-gold");
  await open("Model Room");
  await frame.getByText(/\$51K|\$51\.1K|51,129/).first().waitFor();
  await capture("04-model-validation");
  await open("Evidence Vault");
  const evidence = frame.getByText(/A-INSPECT.*M-1158/).first();
  await evidence.scrollIntoViewIfNeeded();
  await capture("05-inspection-evidence");
} catch (error) {
  await capture(privateRun ? "06-private-embed-failed" : "00-embed-failed");
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
