import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(
  process.env.PLAYWRIGHT_MODULE || "playwright-core",
);
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto("http://127.0.0.1:5173");
  await page.getByRole("button", { name: "Skip intro" }).click();
  await page.getByRole("button", { name: "Pause animation" }).click();
  await page.getByRole("button", { name: "Next pose" }).click();
  assert.equal(await page.locator(".spec-controls strong").innerText(), "Duck");
  await page.screenshot({
    path: fileURLToPath(new URL("../desktop.png", import.meta.url)),
    fullPage: true,
  });
  await page.reload();
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await page.getByLabel("Your name").fill("Test user");
  await page.getByLabel("Email", { exact: true }).fill("test@example.test");
  await page.getByLabel("Password", { exact: true }).fill("example-password");
  await page
    .getByRole("button", { name: "Create account", exact: false })
    .click();
  await page.waitForTimeout(500);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("http://127.0.0.1:5173");
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.equal(await page.locator(".spec-canvas video").count(), 0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: fileURLToPath(new URL("../mobile.png", import.meta.url)),
    fullPage: true,
  });
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  for (const type of ["mp4", "webm"]) {
    const media = await page.evaluate(async (type) => {
      const v = document.createElement("video");
      v.muted = true;
      v.src = "/motion/intro." + type;
      await new Promise((resolve, reject) => {
        v.onloadedmetadata = resolve;
        v.onerror = reject;
      });
      return [v.videoWidth, v.videoHeight, v.duration];
    }, type);
    assert.deepEqual(media, [1920, 1080, 8]);
  }
  assert.deepEqual(errors, []);
  console.log(
    "PASS · intro dismissal, pose controls, responsive layout, reduced motion, MP4 and WebM decoding, zero runtime errors",
  );
} finally {
  await browser.close();
}
