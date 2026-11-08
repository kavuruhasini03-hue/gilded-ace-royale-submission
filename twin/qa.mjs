import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { chromium } from "../embed/node_modules/playwright/index.mjs";

const out = new URL(process.env.QA_SCREEN_DIR || "../docs/screens/views/",import.meta.url);
const publicDir = new URL("../embed/public/",import.meta.url);
await mkdir(out,{recursive:true});
const server = createServer(async (req,res)=>{
  const dataset = req.url==="/gold.json";
  res.writeHead(200,{"Content-Type":dataset?"application/json":"text/html; charset=utf-8"})
    .end(await readFile(new URL(dataset?"gold.json":"index.html",publicDir)));
});
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const base=process.env.QA_ORIGIN || "http://127.0.0.1:"+server.address().port;
const browser=await chromium.launch({channel:"chrome",headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:"reduce",colorScheme:"dark"});
const page=await context.newPage();
await (await context.newCDPSession(page)).send("Network.setCookieControls",{
  enableThirdPartyCookieRestriction:true,disableThirdPartyCookieMetadata:true,disableThirdPartyCookieHeuristics:true
});
const errors=[];
page.on("pageerror", error=>errors.push(error.message));
const capture = (name,fullPage=true)=>page.screenshot({path:new URL(name+".png",out).pathname,fullPage});
const open = async slug=>{
  await page.locator('nav a[href="#/'+slug+'"]').click();
  await page.waitForFunction(value=>location.hash==="#/"+value &&
    document.querySelector('nav a[aria-current="page"]')?.hash==="#/"+value,slug);
};
const filter = () => page.getByRole("button",{name:"Apply filters"}).click();
const dates = async (from,to)=>{
  await page.getByLabel("From",{exact:true}).fill(from);
  await page.getByLabel("Through",{exact:true}).fill(to);
  await filter();
};
const decode = d=>d.rows.map(row=>Object.fromEntries(d.columns.map((c,i)=>[c,row[i]])));
try {
  await page.goto(base+"/#/leak");
  await page.locator("#downtime-total").waitFor();
  const hours=(await page.locator("#downtime-hour svg text").allTextContents()).filter(value=>/^\d{2}:00$/.test(value));
  assert.deepEqual(hours,Array.from({length:24},(_,h)=>String((h+6)%24).padStart(2,"0")+":00"));
  assert.equal(await page.locator("main h2").count(),1);
  assert.equal(await page.getByLabel("Music",{exact:true}).isChecked(),false);
  assert.equal(await page.getByLabel("Sound",{exact:true}).isChecked(),false);
  await page.getByLabel("Sound",{exact:true}).check();
  await page.reload();
  await page.locator("#downtime-total").waitFor();
  assert.equal(await page.getByLabel("Sound",{exact:true}).isChecked(),true);
  await page.getByLabel("Sound",{exact:true}).uncheck();
  await page.evaluate(()=>document.fonts.ready);
  const gold=JSON.parse(await readFile(new URL("../embed/.gold-export.json",import.meta.url),"utf8"));
  await open("verdict");
  for(const expected of decode(gold.kpi_expected)){
    await dates(expected.start,expected.end);
    for(const [key,value] of Object.entries(expected)){
      if(["start","end"].includes(key)) continue;
      const name=key.replaceAll("_","-");
      const digits=["coin","luck","leak","cash_kept"].includes(key)?2:8;
      const actual=await page.locator('[data-kpi="'+name+'"]').getAttribute("data-value");
      assert.equal(actual,Number(value).toFixed(digits),name+" in "+expected.start+" to "+expected.end);
    }
  }
  await page.getByRole("button",{name:"Pull the lever"}).click();
  const dealt=page.locator("#deal-status [data-machine]");
  await dealt.click();
  assert.match(await page.getByRole("dialog").innerText(),/06:00 → 06:00/);
  await page.keyboard.press("Escape");
  await dates("2025-04-01","2025-06-30");
  assert.equal(await page.locator('[data-kpi="coin"]').textContent(),"$124,003,503.70");
  await capture("judge-01-dates");
  await open("demand");
  assert.equal(await page.getByLabel("From",{exact:true}).inputValue(),"2025-04-01");
  assert.equal(await page.evaluate(()=>scrollY),0);
  await page.goBack();
  await page.locator("#bridge").waitFor();
  await page.goForward();
  await page.locator("#slot-map").waitFor();
  await page.getByLabel("Zone",{exact:true}).selectOption("Hotel Corridor");
  await page.getByLabel("Bank",{exact:true}).selectOption("Hotel Corridor · Bank 40");
  await filter();
  const marker=page.locator("#slot-map circle").first();
  await marker.click();
  assert.match(await page.getByRole("dialog").innerText(),/Hotel Corridor · Bank 40/);
  assert.match(await page.getByRole("dialog").innerText(),/06:00 → 06:00/);
  await capture("judge-02-bank-timeline",false);
  await page.keyboard.press("Escape");
  await page.getByRole("button",{name:"Reset",exact:true}).click();
  await open("players");
  await page.getByLabel("Tier",{exact:true}).selectOption("Gold");
  await filter();
  const tiers=await page.locator("#player-segments tbody tr td:first-child").allTextContents();
  assert.ok(tiers.length>0 && tiers.every(t=>t==="Gold"));
  await capture("judge-03-gold");
  const region=await page.locator("#region option").nth(1).getAttribute("value");
  const age=await page.locator("#age option").nth(1).getAttribute("value");
  await page.getByLabel("Home region").selectOption(region);
  await page.getByLabel("Age band").selectOption(age);
  await filter();
  await open("comps");
  assert.equal(await page.getByLabel("Home region").inputValue(),region);
  assert.equal(await page.getByLabel("Age band").inputValue(),age);
  await page.getByRole("button",{name:"Reset",exact:true}).click();
  await open("model");
  assert.match(await page.locator("#model-score").innerText(),/55,270\.94/);
  await capture("judge-04-model");
  await open("plan");
  const card=page.locator(".plan-card").first();
  await card.click();
  assert.equal(await card.getAttribute("aria-pressed"),"true");
  await capture("plan-flipped",false);
  await card.click();
  await page.getByRole("button",{name:"M-1158 evidence",exact:true}).first().click();
  await page.locator("#evidence-match").waitFor();
  assert.match(await page.locator("#evidence-match").innerText(),/M-1158/);
  await capture("judge-04-evidence");
  for(const slug of ["verdict","luck","demand","leak","players","comps","plan","model","evidence"]){
    await open(slug);
    assert.equal(await page.locator("main h2").count(),1,slug);
    assert.equal(await page.getByText("No rows match these filters.",{exact:true}).count(),0,slug);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),1440,slug);
    assert.ok(!(await page.locator("body").innerText()).includes(String.fromCharCode(8212)),slug+" contains an em dash");
    await capture(slug);
  }
  await page.setViewportSize({width:390,height:844});
  await open("verdict");
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
  await capture("mobile",false);
  assert.deepEqual(errors,[]);
  console.log("PASS: exact Gold KPIs, nine views, history and deep links, guest filters, audio preferences, and judge captures.");
} catch(error){
  console.error("Active route:",new URL(page.url()).hash,"Browser errors:",errors);
  throw error;
} finally {
  await browser.close();
  server.close();
}
