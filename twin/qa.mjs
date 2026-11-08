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
  const hours=(await page.locator("#downtime-hour svg text").allTextContents()).filter(value=>/^\d{1,2}[ap]$/.test(value));
  assert.deepEqual(hours,Array.from({length:24},(_,h)=>(((h+6)%12)||12)+((h+6)%24<12?"a":"p")));
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
  assert.deepEqual(await page.locator(".house-verdict p").allTextContents(),[
    "We recommend not replacing any of the ten lowest-earning machines in July. Their low earnings come mostly from the Back Forty's lost foot traffic and from game settings, so we spend $10,500 on three tests: new signage for the Back Forty, a payout check on machine M-1158, and moving machine M-1184 to a busier spot to learn whether its weakness is the spot or the machine. We keep $89,500 in reserve.",
    "Nine of the ten machines are in the Back Forty, an area that lost foot traffic when its entrance walkway was closed for renovation from March 3 to April 7. Most of their shortfall comes from their location and from game settings that keep less of each bet by design, not from faulty machines."
  ]);
  const prepared=page.locator(".pit-boss-answers").getByText("How much should we spend in July?",{exact:true});
  await prepared.click();
  assert.match(await page.locator(".pit-boss-answers details[open]").innerText(),/\$10,500.*\$89,500/);
  await prepared.click();
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
  await dates("2025-01-01","2025-06-30");
  for (const [name,label] of Object.entries({coin:"$248.9M",hold:"9.50%","theo-hold":"9.46%",luck:"$92.8K",leak:"$98.1K"}))
    assert.equal(await page.locator('[data-kpi="'+name+'"]').textContent(),label);
  await page.getByRole("button",{name:"Pull the lever"}).click();
  const dealt=page.locator("#deal-status [data-machine]");
  await dealt.click();
  assert.match(await page.getByRole("dialog").innerText(),/06:00 → 06:00/);
  await page.keyboard.press("Escape");
  await dates("2025-04-01","2025-06-30");
  assert.equal(await page.locator('[data-kpi="coin"]').textContent(),"$124.0M");
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
  const forecast=page.locator("#forecast-review");
  await forecast.waitFor();
  assert.match(await forecast.innerText(),/66\.5K/);
  await forecast.screenshot({path:new URL("model-comparison.png",out).pathname});
  assert.match(await page.locator("#forecast-review").innerText(),/51\.1K/);
  await capture("judge-04-model");
  await open("plan");
  const allocation=page.locator(".budget-allocation");
  await allocation.focus();
  assert.equal(await allocation.evaluate(el=>el===document.activeElement),true);
  const cage=decode(gold.cage)[0];
  const currency=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0});
  assert.ok((await allocation.innerText()).includes(currency.format(cage.spent_usd)));
  assert.ok((await allocation.innerText()).includes(currency.format(cage.kept_usd)));
  assert.equal(await page.locator("#unfunded-options tbody tr").count(),8);
  assert.equal(await page.locator(".plan-card").count(),4);
  assert.match(await allocation.innerText(),/signs for Back Forty.*M-1158.*M-1184/);
  assert.equal(await page.locator("#cage-slip tbody tr").filter({hasText:"L-07-3"}).first().getByText("Yes",{exact:true}).count(),1);
  await page.locator("#budget-allocation").screenshot({path:new URL("budget-allocation.png",out).pathname});
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
    const text=await page.locator("body").innerText();
    assert.doesNotMatch(text,/\b(?:NaN|undefined|null|No data)\b/,slug+" contains an invalid value");
    assert.doesNotMatch(text,/\d+\.\d{7,}/,slug+" contains an unformatted number");
    assert.ok(!text.includes(String.fromCharCode(8212)),slug+" contains an em dash");
    assert.doesNotMatch(text,/replace none|underpowered|\bconfigs\b|\bGM(?:['’]s)?\b/i,slug+" contains legacy copy");
    await capture(slug);
  }
  await page.setViewportSize({width:390,height:844});
  await open("verdict");
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
  await capture("mobile",false);
  await open("plan");
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
  await page.locator("#budget-allocation").screenshot({path:new URL("budget-phone.png",out).pathname});
  for (const slug of ["luck","demand","leak","players","comps","model","evidence"]) {
    await open(slug);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390,slug+" phone width");
  }
  assert.deepEqual(errors,[]);
  console.log("PASS: exact Gold KPIs, nine views, history and deep links, guest filters, audio preferences, and judge captures.");
} catch(error){
  console.error("Active route:",new URL(page.url()).hash,"Browser errors:",errors);
  throw error;
} finally {
  await browser.close();
  server.close();
}
