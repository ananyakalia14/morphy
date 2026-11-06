import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||"playwright-core");
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||"C:/Program Files/Google/Chrome/Application/chrome.exe",headless:true});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto("http://127.0.0.1:5173/#explore");
 await page.getByRole("combobox").selectOption("custom");
 await page.getByLabel("Your question",{exact:true}).fill("What is the sum of paid order amounts? Return a single total.");
 await page.getByRole("button",{name:"Generate & run"}).click();
 await page.locator("tbody tr").first().waitFor({timeout:195000});
 assert.equal(Number((await page.locator("tbody td").first().innerText()).replaceAll(",","")),11650);
 await page.getByRole("button",{name:"Governed SQL",exact:true}).click();
 assert.ok((await page.locator(".compiled pre").innerText()).includes("APAC"));
 await page.screenshot({path:fileURLToPath(new URL("../ai-workbench.png",import.meta.url)),fullPage:true});
 console.log("PASS · browser → real Qwen → restored SQL → governed SQLite → correct paid APAC total");
} finally {await browser.close()}

