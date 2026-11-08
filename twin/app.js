"use strict";
const $ = id => document.getElementById(id);
const escape = value => String(value ?? "Unavailable").replace(/\bGM\b/g,"general manager").replaceAll(String.fromCharCode(8212), ". ").replace(/[&<>"']/g, char =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const fmt = new Intl.NumberFormat("en-US", {maximumFractionDigits: 2});
const usd = new Intl.NumberFormat("en-US", {style:"currency",currency:"USD"});
const axisMoney = new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",notation:"compact",maximumFractionDigits:2});
const pct = new Intl.NumberFormat("en-US", {style:"percent",maximumFractionDigits:2});
const unique = values => [...new Set(values.filter(Boolean))].sort();
const sum = (rows, key) => rows.reduce((total, row) => total + Number(row[key] ?? 0), 0);
const ratio = (a,b) => b ? a / b : null;
const colors = ["#e3b850","#6fb6ff","#c79bff","#ff5f57","#ffa24c","#fbf6e9","#5fd39a"];
const suitColor = label => ({"♦":colors[6],"♣":colors[1],"♥":colors[4],"⚙":colors[2],"♠":colors[0],"🔍":colors[3]})[Array.from(label || "")[0]] ?? colors[5];
const filters = {start:"2025-01-01",end:"2025-06-30",zone:"",bank:"",tier:"",region:"",age:""};
let data, pages, review, insights, active = 0, selectedMachine = "", evidenceMachine = "";
const dateIn = value => value && value.slice(0,10) >= filters.start && value.slice(0,10) <= filters.end;
const machineIn = row => dateIn(row.gaming_date) && (!filters.zone || row.zone_name === filters.zone)
  && (!filters.bank || row.bank_name === filters.bank) && (!selectedMachine || row.machine_id === selectedMachine);

function kpis(machine, floor) {
  const coin = sum(machine,"coin_in_usd"), theo = sum(machine,"theo_usd"), win = sum(machine,"house_win_usd");
  const leak = sum(machine,"leak_usd"), luck = sum(machine,"luck_residual_usd");
  return {health:ratio(theo,theo+leak+sum(machine,"location_opportunity_usd")),coin,hold:ratio(win,coin),
    "theo-hold":ratio(theo,coin),luck,leak,"comp-kpi":ratio(sum(floor,"comp_cost_usd"),sum(floor,"tracked_theo_usd")),
    "sigma-kpi":ratio(luck,Math.sqrt(sum(machine,"luck_variance_usd2"))),"cash-kept":data.cage[0].kept_usd};
}
function groups(rows, keys, fields) {
  const result = new Map();
  for (const row of rows) {
    const id = JSON.stringify(keys.map(key => row[key]));
    if (!result.has(id)) result.set(id, Object.fromEntries(keys.map(key => [key,row[key]])));
    const group = result.get(id);
    for (const [alias, source] of Object.entries(fields)) group[alias] = (group[alias] || 0) + Number(row[source] ?? 0);
  }
  return [...result.values()];
}
function table(columns, rows) {
  if (!rows.length) return '<p role="status" class="muted">No rows match these filters.</p>';
  const cell = (value,column,row) => {
    if (value == null) return "Unavailable";
    if (column.fieldName === "machine_id") return '<button class="link" data-machine="' + escape(value) + '">' + escape(value) + '</button>';
    if (column.fieldName === "verdict_chip") return '<span class="chip" style="color:' + suitColor(value) + '">' + escape(value) + '</span>';
    if (typeof value === "boolean") return value ? "Yes" : "No";
    const friendly = {constant_baseline:"Constant baseline",weekday_event_holiday:"Weekday, event, and holiday model",
      relative_coin_in_pct:"Change in tracked wagers relative to untracked wagers (%)",
      relative_coin_in_usd_week:"Change in tracked wagers relative to untracked wagers ($ per week)",
      carded_share_pp:"Change in the tracked share of wagers (percentage points)",
      tracked_theo_per_player_raw_usd:"Raw change in expected win per tracked player ($)",
      tracked_theo_per_player_control_adjusted_usd:"Change in expected win per tracked player after comparison ($)",
      face:"Face value",economic:"Economic cost"};
    if (typeof value==="string") value=value.replace(/\bGM\b/g,"general manager");
    if (typeof value==="string" && friendly[value]) return friendly[value];
    if (column.fieldName==="action_type_id" && row.action_name) return escape(row.action_name);
    if (["claim","result","alternative_tested","limitation"].includes(column.fieldName)) {
      const sentence = String(value).replace(/\bUSD (-?\d+(?:\.\d+)?)/g,(_,amount)=>usd.format(Number(amount)))
        .replace(/\bvs\b/g,"compared with").replace(/\b90% interval\b/g,"90% uncertainty range")
        .replace(/\bcarded\b/g,"tracked").replace(/\buncarded\b/g,"untracked").trim();
      return escape(/[.!?]$/.test(sentence)?sentence:sentence+".");
    }
    if (column.format?.type === "number-currency") return usd.format(value);
    if (column.format?.type === "number-percent") return pct.format(value);
    if (column.fieldName === "target_label" && row.action_type_id === "A-INSPECT")
      return '<button class="link" data-evidence="' + escape(row.target_id) + '" aria-label="' + escape(row.target_id) + ' evidence">' + escape(value) + ' ↗</button>';
    return typeof value === "number" ? fmt.format(value) : escape(value);
  };
  return '<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable data table"><table><thead><tr>'
    + columns.map(c => '<th scope="col">' + escape(c.displayName) + '</th>').join("") + '</tr></thead><tbody>'
    + rows.map(row => '<tr' + (evidenceMachine && row.claim?.includes(evidenceMachine) ? ' class="focus-row" id="evidence-match"' : '') + '>'
      + columns.map(c => '<td'+(c.format?.type === 'number-currency' ? ' class="money"' : '')+'>' + cell(row[c.fieldName],c,row) + '</td>').join("") + '</tr>').join("") + '</tbody></table></div>';
}
const columns = (x,series) => [x,...series].map(([fieldName,displayName,format]) => ({fieldName,displayName,format}));
const currency = {type:"number-currency"};
const percent = {type:"number-percent"};
const fallback = (cols,rows) => '<details><summary>Show chart data</summary>' + table(cols,rows) + '</details>';

function line(title, rows, x, series, {shade, shadeEnd, numeric = false} = {}) {
  rows = rows.filter(row => row[x[0]] != null).sort((a,b) => numeric ? a[x[0]]-b[x[0]] : String(a[x[0]]).localeCompare(b[x[0]]));
  if (!rows.length) return table(columns(x,series),[]);
  const values = rows.flatMap(row => series.map(([k]) => row[k]).filter(v => v != null).map(Number));
  if (!values.length) return table(columns(x,series),[]);
  const low = Math.min(...values), high = Math.max(...values);
  const xx = index => 75 + index / Math.max(1,rows.length-1)*610;
  const yy = value => 185-(value-low)/(high-low || 1)*152;
  const formatY = value => series[0][2] === currency ? axisMoney.format(value) : series[0][2] === percent ? pct.format(value) : fmt.format(value);
  const intervals = [0,.5,1];
  const grid = intervals.map(p => {
    const v = low+(high-low)*p, y = yy(v);
    return '<path d="M75 '+y+'H685" stroke="#55736a"/><text x="68" y="'+(y+4)+'" text-anchor="end">'+escape(formatY(v))+'</text>';
  }).join("");
  const startShade = shade ? rows.findIndex(row => row[x[0]] >= shade) : -1;
  const afterShade = shadeEnd ? rows.findIndex(row => row[x[0]] > shadeEnd) : -1;
  const overlay = startShade < 0 ? "" : '<rect x="'+xx(startShade)+'" y="22" width="'+((afterShade<0?695:xx(afterShade))-xx(startShade))+'" height="170" fill="#24443a"/>';
  const paths = series.map(([key],i) => {
    const points = rows.map((row,j) => row[key] == null ? null : [xx(j),yy(Number(row[key]))]);
    const path = points.map((point,j) => point ? (points[j-1] ? "L" : "M")+point.join(",") : "").join("");
    return '<path d="'+path+'" fill="none" stroke="'+colors[i]+'" stroke-width="2" stroke-dasharray="'+["none","6 3","2 3"][i%3]+'"/>';
  }).join("");
  const ticks = [...new Set([0,Math.floor((rows.length-1)/2),rows.length-1])].map(i => {
    const value = rows[i][x[0]], label = numeric && x[0].includes("share") ? pct.format(value) : String(value).slice(0,10);
    return '<text x="'+xx(i)+'" y="217" text-anchor="'+(i===rows.length-1&&i!==0?"end":i===0?"start":"middle")+'">'+escape(label)+'</text>';
  }).join("");
  return '<svg class="chart" viewBox="0 0 705 230" role="img" aria-label="'+escape(title)+'">'+overlay+grid+paths+ticks+'</svg>'
    + '<div class="series">'+series.map(([,label],i) => '<span style="color:'+colors[i]+'">'+escape(label)+'</span>').join("")+'</div>'
    + fallback(columns(x,series),rows);
}
function waterfall(rows) {
  const parts = [["Potential",sum(rows,"potential_theo_usd"),false],["♥ Leak",-sum(rows,"leak_usd"),true],
    ["♣ Location",sum(rows,"location_usd"),true],["⚙ Lineup",sum(rows,"lineup_usd"),true],
    ["♠ Machine",sum(rows,"machine_specific_usd"),true],["Theo",sum(rows,"theo_usd"),false],
    ["♦ Luck",sum(rows,"luck_residual_usd"),true],["Actual",sum(rows,"house_win_usd"),false]];
  let running = 0;
  const bars = parts.map(([label,value,change]) => {
    const start = change ? running : 0;
    running = start+value;
    return {label,value,start,end:running};
  });
  const low = Math.min(0,...bars.map(b=>Math.min(b.start,b.end))), high = Math.max(0,...bars.map(b=>Math.max(b.start,b.end)));
  const xx = v => 147+(v-low)/(high-low || 1)*350;
  return '<svg class="chart" viewBox="0 0 705 273" role="img" aria-label="Waterfall from potential theo to actual win">'
    + bars.map((b,i) => '<text x="4" y="'+(24+33*i)+'">'+escape(b.label)+'</text><rect x="'+Math.min(xx(b.start),xx(b.end))
      +'" y="'+(9+33*i)+'" width="'+Math.max(1,Math.abs(xx(b.start)-xx(b.end)))+'" height="21" rx="3" fill="'+
      [colors[0],colors[3],colors[1],colors[4],colors[5],colors[0],colors[2],colors[6]][i]+'"/>'
      +'<text x="695" y="'+(24+33*i)+'" text-anchor="end">'+usd.format(b.value)+'</text>').join("")
    + '</svg>'+fallback(columns(["label","Component"],[["value","Amount",currency]]),bars);
}
function scatter(title,rows,x,y,{map=false,funnel=false}={}) {
  if (!rows.length) return table(columns(["machine_id","Machine"],[x,y]),[]);
  const xs = rows.map(r=>Number(r[x[0]])), ys = rows.map(r=>Number(r[y[0]]));
  const xmin = funnel ? 0 : Math.min(...xs), xmax = Math.max(...xs);
  const ymin = funnel ? Math.min(-3*xmax,...ys) : Math.min(...ys), ymax = funnel ? Math.max(3*xmax,...ys) : Math.max(...ys);
  const xx = v => 55+(v-xmin)/(xmax-xmin || 1)*605;
  const yy = v => 195-(v-ymin)/(ymax-ymin || 1)*160;
  const guides = funnel ? [-3,-2,2,3].map(k=>'<path d="M'+xx(0)+' '+yy(0)+'L'+xx(xmax)+' '+yy(k*xmax)
      +'" fill="none" stroke="#9faea6" stroke-dasharray="'+(Math.abs(k)===2?"4 3":"2 5")+'"/>').join("") : "";
  const points = rows.map((r,i) => '<circle role="button" tabindex="0" aria-label="'+escape(r.machine_id+(map ? " · "+r.bank_name : ""))
    +'" data-machine="'+escape(r.machine_id)+'" cx="'+xx(xs[i])+'" cy="'+yy(ys[i])+'" r="'+(map?5:4)+'" fill="'+suitColor(r.verdict_chip)+'"><title>'
    +escape(r.machine_id+' · '+r.verdict_chip)+'</title></circle>').join("");
  return '<svg class="chart" viewBox="0 0 705 245" role="group" aria-label="'+escape(title)+'"><path d="M55 35V195H660" fill="none" stroke="#9faea6"/>'
    + guides+points+'<text x="360" y="231" text-anchor="middle">'+escape(x[1])+'</text><text x="54" y="22">'+escape(y[1])
    + '</text></svg>'+fallback(columns(["machine_id","Machine"],[x,y,["bank_name","Bank"],["verdict_chip","Verdict"]]),rows);
}
function hourLabel(hour) { return String((hour+6)%24).padStart(2,"0")+":00"; }
function heat(title,rows,kind) {
  const grouped = groups(rows,["zone_name","gaming_hour"],{entries:"entries",coverage:"coverage_minutes",loss:"lost_theo_usd"});
  for (const row of grouped) row.value = kind === "traffic" ? ratio(60*row.entries,row.coverage) : row.loss;
  if (!grouped.length) return table([],[]);
  const zones = unique(grouped.map(row=>row.zone_name)), max = Math.max(1,...grouped.map(row=>row.value ?? 0));
  const lookup = new Map(grouped.map(row=>[row.zone_name+row.gaming_hour,row.value]));
  const marks = zones.map((zone,i) => '<text x="3" y="'+(37+27*i)+'">'+escape(zone)+'</text>'
    +Array.from({length:24},(_,h) => {
      const value = lookup.get(zone+h);
      return '<rect x="'+(146+h*22)+'" y="'+(21+27*i)+'" width="20" height="22" rx="2" stroke="'+(value==null?"#24443a":colors[kind==="traffic"?1:3])+'" fill="'
        +(value==null?"#24443a":colors[kind==="traffic"?1:3])+'" fill-opacity="'+(value==null?1:.24+.76*value/max)+'"><title>'
        +escape(zone+" · "+hourLabel(h)+" · "+(value==null?"Not covered":fmt.format(value)))+'</title></rect>';
    }).join("")).join("");
  const axis = [0,4,8,12,16,20,23].map(h=>'<text x="'+(155+h*22)+'" y="15" text-anchor="middle">'+hourLabel(h)+'</text>').join("");
  return '<svg class="chart" viewBox="0 0 690 '+(28+27*zones.length)+'" role="img" aria-label="'+escape(title)+'">'+axis+marks+'</svg>'
    +fallback(columns(["zone_name","Zone"],[["hour","Gaming hour"],["value",kind==="traffic"?"Entries / covered hour":"Lost theo",kind==="traffic"?null:currency]]),
      grouped.map(r=>({...r,hour:hourLabel(r.gaming_hour)})).sort((a,b)=>a.zone_name.localeCompare(b.zone_name)||a.gaming_hour-b.gaming_hour));
}
function bars(title,rows,label,value,format) {
  if (!rows.length) return table([],[]);
  const max = Math.max(1,...rows.map(r=>Math.abs(r[value])));
  return '<svg class="chart" viewBox="0 0 705 '+(rows.length*29+12)+'" role="img" aria-label="'+escape(title)+'">'
    + rows.map((row,i) => {
      const v = row[value], w = Math.abs(v)/max*150, y = 7+i*29;
      return '<text x="4" y="'+(y+15)+'">'+escape(row[label])+'</text><rect x="'+(455-(v<0?w:0))+'" y="'+y
        +'" width="'+Math.max(1,w)+'" height="20" fill="'+colors[v<0?3:1]+'"/><text x="699" y="'+(y+15)
        +'" text-anchor="end">'+escape(format===currency?usd.format(v):fmt.format(v))+'</text>';
    }).join("")+'</svg>'+fallback(columns([label,"Group"],[[value,"Value",format]]),rows);
}
const stable = name => data[name] || [];
const datasets = {
  tribunal: rows => groups(rows.filter(r=>filters.zone || filters.bank || selectedMachine || r.gm_rank<=10),["machine_id","gm_rank","last_bank_name","verdict_chip"],{win:"house_win_usd"}).sort((a,b)=>a.gm_rank-b.gm_rank).slice(0,10),
  "player-segments": () => groups(stable("segments").filter(r=>dateIn(r.gaming_date) && guestIn(r)),
    ["tier_end","theo_decile"],{wagers:"coin_in_usd",payout:"payout_usd",net:"player_net_usd",theo:"theo_usd",luck:"player_luck_usd"})
    .sort((a,b)=>a.tier_end.localeCompare(b.tier_end)||a.theo_decile-b.theo_decile)
};
const machineGroups = rows => groups(rows,["machine_id","verdict_chip"],{variance:"luck_variance_usd2",luck:"luck_residual_usd",
  theo:"theo_usd",win:"house_win_usd",hours:"available_hours",effect:"machine_specific_usd"});
function charts(name,title,rows) {
  switch(name) {
    case "bridge": return rows.length ? waterfall(rows) : table([],[]);
    case "luck-funnel": return scatter(title,machineGroups(rows).map(r=>({...r,sigma:Math.sqrt(r.variance)})),["sigma","Expected sigma ($)"],["luck","Luck residual ($)"],{funnel:true});
    case "actual-theo": {
      const shortlist=new Set(stable("comparison").map(r=>r.machine_id));
      return scatter(title,machineGroups(rows).filter(r=>shortlist.has(r.machine_id)),["theo","Expected win ($)"],["win","Actual win ($)"]);
    }
    case "peers": {
      const rates = groups(rows,["config_id","machine_id","verdict_chip"],{theo:"theo_usd",hours:"available_hours"})
        .filter(r=>r.hours>0).map(r=>({...r,rate:r.theo/r.hours}));
      const configs = unique(rates.map(r=>r.config_id));
      return scatter(title,rates.map(r=>({...r,config:configs.indexOf(r.config_id)+1})),
        ["config","Configuration index"],["rate","Theo per available hour ($)"]);
    }
    case "slot-map": {
      const positions = new Map(rows.map(r=>[JSON.stringify([r.machine_id,r.bank_name,r.x_m,r.y_m]),r]));
      return scatter(title,[...positions.values()],["x_m","Floor X (m)"],["y_m","Floor Y (m)"],{map:true});
    }
    case "traffic-heat":
    case "leak-heat": {
      const focus = rows.length && (filters.bank || selectedMachine) ? new Set(rows.map(r=>r.zone_name)) : null;
      return heat(title,stable("traffic").filter(r=>dateIn(r.gaming_date) && (!filters.zone || r.zone_name===filters.zone)
        && (!focus || focus.has(r.zone_name))),name==="traffic-heat"?"traffic":"leak");
    }
    case "demand-timeline": return line(title,stable("demand").filter(r=>dateIn(r.gaming_date)),["gaming_date","Gaming date"],
      [["coin_in_usd","Actual",currency],["forecast_usd","Forecast",currency]],{shade:"2025-03-03",shadeEnd:"2025-04-06"});
    case "walkway-did": {
      const phases=stable("machine").filter(r=>dateIn(r.gaming_date)).map(r=>({...r,day:1,
        period:r.gaming_date<"2025-03-03"?"1 Before":r.gaming_date<"2025-04-07"?"2 Closed":"3 After",
        side:r.zone_id==="Z-B40"?"back":"rest"}));
      const baseline=stable("walkway").find(r=>r.phase==="pre");
      const result=groups(phases,["period","side"],{wagers:"coin_in_usd",days:"day"});
      const periods=unique(result.map(r=>r.period)).map(period=>({period,...Object.fromEntries(
        result.filter(r=>r.period===period).map(r=>[r.side,100*r.wagers/r.days/(r.side==="back"?baseline.back_forty_rate:baseline.control_rate)]))}));
      return line(title,periods,["period","Closure phase"],[["back","Back Forty"],["rest","Rest of floor"]]);
    }
    case "fault-hour": {
      const selected = new Set(rows.map(r=>r.machine_id+"|"+r.gaming_date));
      const hits = stable("fault").filter(r=>selected.has(r.machine_id+"|"+r.gaming_date));
      const rollup = groups(hits.map(r=>({...r,n:1})),["gaming_hour"],{wait:"wait_seconds",work:"work_seconds",n:"n"})
        .map(r=>({...r,wait:r.wait/r.n/3600,work:r.work/r.n/3600}));
      return line(title,rollup,["gaming_hour","Hours after 06:00"],[["wait","Wait hours"],["work","Work hours"]],{numeric:true});
    }
    case "leak-month": {
      const rollup = groups(rows.map(r=>({...r,month:r.gaming_date.slice(0,7)})),["month","manufacturer"],{hours:"downtime_hours"});
      const makers = unique(rollup.map(r=>r.manufacturer));
      const months = unique(rollup.map(r=>r.month)).map(month=>({month,...Object.fromEntries(
        rollup.filter(r=>r.month===month).map(r=>[r.manufacturer,r.hours]))}));
      return line(title,months,["month","Month"],makers.map(m=>[m,m]));
    }
    case "concentration-curve": {
      if(filters.start==="2025-01-01" && filters.end==="2025-06-30" && !filters.tier && !filters.region && !filters.age)
        return line(title,stable("ladder"),["cumulative_player_share","Cumulative player share"],
          [["cumulative_theo_share","Expected win share",percent],["cumulative_coin_in_share","Wager share",percent]],{numeric:true});
      const selected=stable("segments").filter(r=>dateIn(r.gaming_date)&&guestIn(r));
      const deciles=groups(selected,["theo_decile"],{coin:"coin_in_usd",theo:"theo_usd"}).sort((a,b)=>a.theo_decile-b.theo_decile);
      const totalCoin=sum(deciles,"coin"), totalTheo=sum(deciles,"theo");
      let coin=0,theo=0;
      const shares=deciles.map(r=>({decile:r.theo_decile,coin:ratio(coin+=r.coin,totalCoin),theo:ratio(theo+=r.theo,totalTheo)}));
      return '<p class="muted">For this selection, the curve combines the fixed ranking groups. It shows how much play came from each group.</p>'
        +line(title,shares,["decile","Expected win group"],[["theo","Expected win share",percent],["coin","Wager share",percent]],{numeric:true});
    }
    case "net-histogram": {
      const full=filters.start==="2025-01-01" && filters.end==="2025-06-30" && !filters.tier && !filters.region && !filters.age;
      const rows=[...stable("hist")].sort((a,b)=>a.bin_id-b.bin_id);
      return full ? bars(title,rows,"band","observations") : table(columns(["band","Six-month result"],[["observations","Players"]]),rows);
    }
    case "action-board": return bars(title,stable("actions").map(r=>({...r,label:r.action_type_id+" "+r.target_label})),"label","expected_net_usd",currency);
    case "model-holdout": return line(title,stable("forecast").filter(r=>dateIn(r.gaming_date)),["gaming_date","Gaming date"],
      [["actual_usd","Actual",currency],["forecast_usd","Weekday model",currency],["baseline_usd","Baseline",currency]],{shade:"2025-05-01"});
    default: return "";
  }
}
const layout = {
  verdict:["health","coin","hold","theo-hold","luck","leak","comp-kpi","sigma-kpi","cash-kept","tribunal","bridge","adjusted"],
  luck:["luck-funnel","actual-theo","mean-reversion","peers"],
  demand:["monthly-demand","demand-bridge","slot-map","demand-timeline","traffic-heat","walkway-did","lasting-gap","zone-drivers","high-limit"],
  leak:["downtime-total","downtime-month","downtime-hour","downtime-maker","fault-hour","leak-heat"],
  players:["player-segments","concentration-curve","top-shares","player-outcomes","net-histogram"],
  comps:["comp-price","comp-rates","points-exposure","comp-weekly","comp-control"],
  plan:["budget-allocation","unfunded-options","spent","kept","hold-ref","action-board","cage-slip","annual-options","tech-compare","tech-sensitivity"],
  model:["forecast-review","model-holdout","model-score","model-residual"],
  evidence:["review-evidence","claims"]
};
const extraCopy = {
  "budget-allocation":["Most of the July budget stays in reserve","The thin slice is the funded inspection. The labels show the amount and share on both sides."],
  "unfunded-options":["What we chose to leave unfunded","Net value includes cost and the estimated benefit. Pilot and survey values describe what their findings might be worth."],
  "forecast-review":["A trend checks whether the weekday forecast can handle falling demand","We compared the two ridge models on April, using January through March to fit them. Then we froze the trend forecast through April 30 before checking May and June."],
  "review-evidence":["The forecast sensitivity leaves the staffing decision unchanged","We repriced the expected recovery using the trend forecast. Even a generous upper bound does not cover the staffing package."],
  "monthly-demand":["Compare wagers per day by month and zone","The table divides total wagers and expected win by the number of gaming dates selected in each month."],
  "demand-bridge":["Weekdays, events and the closure explain part of the change","This floor-wide table separates each month’s wagers per day into its weekday mix, event days, the closure, and everything else."],
  "lasting-gap":["Back Forty had a lasting gap after the closure","This compares January with the weeks after the walkway reopened. It describes what happened, and other changes could also explain the gap."],
  "high-limit":["High-Limit Room had fewer visits from its top players","This compares June with January through April. The ranges show how much the estimated change varies when we sample whole weeks."],
  "downtime-total":["Downtime hours and the expected win they cost","The totals use the current date, zone, and bank selection."],
  "downtime-month":["Some months lost more expected win than others","The line adds the estimated missed win by month. A bank selection uses the machine-day totals for that bank."],
  "downtime-hour":["Timing matters for lost expected win","The bars run from 06:00 through 05:00. For a selected bank, the chart shows its zone because hourly totals are available by zone."],
  "downtime-maker":["Compare lost expected win by manufacturer","The table shows downtime hours and missed expected win for the selected dates and machines."],
  "comp-weekly":["Tracked and untracked wagers moved differently","Each line shows weekly wagers as a share of its own pre-May average. The comparison uses complete published weeks within the selected dates and cannot be split by guest group."],
};
const guestIn = row => (!filters.tier || row.tier_end===filters.tier)
  && (!filters.region || row.home_region===filters.region) && (!filters.age || row.age_band===filters.age);
const metric = (key,label,format) => ({fieldName:key,displayName:label,format});
const cohortFields = {coin:"coin_in_usd",payout:"payout_usd",net:"player_net_usd",theo:"theo_usd",luck:"player_luck_usd"};
const monthRows = rows => rows.map(r=>({...r,month:r.gaming_date.slice(0,7),count:1}));
const weekly = date => {
  const monday = new Date(date+"T00:00:00Z");
  monday.setUTCDate(monday.getUTCDate()-(monday.getUTCDay()+6)%7);
  return monday.toISOString().slice(0,10);
};
function compTrend(name,title) {
  const selected = filters.tier || filters.region || filters.age;
  const rows = (selected ? stable("segments").filter(guestIn) : stable("comp_days")).filter(r=>dateIn(r.gaming_date))
    .map(r=>({...r,week:weekly(r.gaming_date),cost:selected?r.cost_usd:r.comp_cost_usd,
      tracked:selected?r.theo_usd:r.tracked_theo_usd}));
  const weeklyRows = groups(rows,["week"],{cost:"cost",tracked:"tracked",floor:"theo_usd",points:"points",face:"face_usd"})
    .map(r=>({...r,price:ratio(r.points,r.face),trackedRate:ratio(r.cost,r.tracked),floorRate:ratio(r.cost,r.floor)}));
  return line(title,weeklyRows,["week","Week starting"],
    name==="comp-price" ? [["price","Points per dollar"]] : [["trackedRate","Tracked expected win",percent],
      ...(!selected?[["floorRate","Floor expected win",percent]]:[])],{shade:"2025-05-05"});
}
function pitBossAnswers() {
  const cage=stable("cage")[0];
  const actions=stable("actions");
  const inspection=actions.find(r=>r.action_type_id==="A-INSPECT" && r.selected);
  const pilot=actions.find(r=>r.action_type_id==="A-COMP-PILOT");
  const threshold=pilot.success_rule.match(/at most ([\d.]+%)/)?.[1];
  const primary=stable("scores").find(r=>r.model==="weekday_event_holiday");
  const baseline=stable("scores").find(r=>r.model==="constant_baseline");
  const reduction=1-primary.mae_usd/baseline.mae_usd;
  const answers=[
    ["How much should we spend in July?", "Fund "+usd.format(cage.spent_usd)+" and keep "+usd.format(cage.kept_usd)+" in reserve.",
      "plan","Open the July plan"],
    ["Why inspect "+inspection.target_id+"?", "The "+usd.format(inspection.cash_cost_usd)+" check can determine whether the payout meter, game settings, or accounting show a repeatable problem. The estimated net value of what we might learn is "+usd.format(inspection.expected_net_usd)+".",
      "evidence","Open the evidence"],
    ["How accurate is the primary forecast?", "Using announcements known by April 30, the model missed by "+usd.format(primary.mae_usd)+" per day on average over "+primary.scored_days+" days. That is "+pct.format(reduction)+" less error than the constant forecast.",
      "model","Open the Model Room"],
    ["Why wait on the comp pilot?", "The proposed trial costs "+usd.format(pilot.cash_cost_usd)+". Fund it when it can reliably detect a change of "+threshold+" or less.",
      "comps","Open the comps view"],
    ["What did downtime cost?", "Across the six-month study, unavailable machines cost an estimated "+usd.format(sum(stable("floor"),"leak_usd"))+" in expected house win.",
      "leak","Open the downtime view"],
  ];
  return '<aside class="card pit-boss-answers" aria-labelledby="pit-boss-heading"><h3 id="pit-boss-heading">Ask the Pit Boss</h3>'
    +'<p class="muted">Choose a question. These prepared answers use the Gold export for the full study and the July decision.</p>'
    +answers.map(([question,answer,route,link])=>'<details><summary>'+escape(question)+'</summary><p>'+escape(answer)
      +' <a href="#/'+route+'">'+escape(link)+'</a></p></details>').join("")+'</aside>';
}
function budgetAllocation() {
  const spent=sum(stable("actions").filter(row=>row.selected),"cash_cost_usd");
  const reserve=data.cage[0].kept_usd;
  const total=spent+reserve, share=100*spent/total;
  const label=(name,amount)=>name+" "+usd.format(amount)+" ("+(100*amount/total).toFixed(1)+"%)";
  const funded=label("Funded",spent), kept=label("Reserve",reserve);
  return '<figure class="budget-allocation" tabindex="0" aria-label="'+escape(funded+". "+kept+". Total "+usd.format(total))+'">'
    +'<div class="budget-callout">'+escape(funded)+'</div><div class="budget-track" aria-hidden="true">'
    +'<span style="width:'+share+'%"></span></div><figcaption>'+escape(kept)+' · Total '+usd.format(total)+'</figcaption></figure>';
}
function unfundedOptions() {
  const reasons={
    "A-TECH-SHIFT":"The expected win recovered by a shorter wait does not cover the staffing cost.",
    "A-MOVE-BANK":"Test whether the bank position explains the gap before moving the machines.",
    "A-REPLACE-LEASE":"Keep this on the long-term watchlist. The July estimate does not cover the cost.",
    "A-COMP-PILOT":"The trial cannot detect a small enough change. Fund it only when the smallest detectable change is at most "+
      (stable("actions").find(row=>row.action_type_id==="A-COMP-PILOT").success_rule.match(/at most ([\d.]+%)/)?.[1] ?? "the planning threshold")+".",
    "A-SURVEY":"The expected value of the survey findings does not cover its cost."
  };
  const annual=new Map(stable("annual").map(r=>[r.action_type_id+"|"+r.target_id,r]));
  const rows=stable("actions").filter(r=>!r.selected && reasons[r.action_type_id] && r.target_id!=="GM-BOTTOM-10")
    .map(r=>({...r,option:r.action_type_id==="A-TECH-SHIFT"?(r.target_id==="Grave"?"Overnight technician shift":"Saturday evening technician shift")
      :r.action_type_id==="A-REPLACE-LEASE"?"Lease "+r.target_label:r.target_label,
      annualNet:["A-COMP-PILOT","A-SURVEY"].includes(r.action_type_id)?null:annual.get(r.action_type_id+"|"+r.target_id)?.expected_net_usd,
      reason:reasons[r.action_type_id]}));
  return table([metric("option","Option"),metric("cash_cost_usd","July cost",currency),metric("expected_net_usd","July net value",currency),
    metric("annualNet","12-month net value",currency),metric("reason","Why it stays unfunded")],rows);
}
function forecastReview() {
  const scores=Object.entries(review.holdout).map(([model,values])=>({model,...values}));
  const bias=Object.entries(review.bias).map(([weekday,values])=>({weekday,...values}));
  return '<p>April average error was '+usd.format(review.april.current.mae)+' for the current model and '+usd.format(review.april.trend.mae)
    +' for the trend model. '+(review.promote?'The trend also reduced error in May and June. It qualifies as a candidate to replace the current model.':'The trend did not improve both tests. The current model remains primary.')+'</p>'
    +table([metric("model","Model"),metric("mae","May–June average dollar error",currency),metric("mape","May–June average percentage error")],scores)
    +'<p>Positive bias means the forecast was too high. These averages use the same 61 days.</p>'
    +table([metric("weekday","Weekday"),...scores.map(row=>metric(row.model,row.model,currency))],bias)
    +'<div class="forecast-disclosure"><h4>Why the primary score changed</h4><p>'+escape(review.disclosure.event)
    +' was announced on May 26, after the April 30 forecast date. The earlier forecast used it on seven June dates. We removed it, refit the model through April 30, froze the forecasts, and rescored the 61 holdout days once.</p>'
    +'<p>Earlier score: '+usd.format(review.disclosure.old.mae)+' and '+review.disclosure.old.mape.toFixed(2)+'%. Corrected primary score: '
    +usd.format(review.holdout["Current ridge"].mae)+' and '+review.holdout["Current ridge"].mape.toFixed(2)
    +'%. The trend lost because it increased error in April and in May and June.</p></div>';
}
function staffingReview() {
  return table([metric("shift","Coverage"),metric("cost","July package",currency),metric("original_recovery","Original expected recovery",currency),
    metric("repriced_recovery","With trend",currency),metric("maximum_recovery","Upper bound",currency)],review.tech)
    +'<p>See the repository evidence ledger for the frozen prediction record and the assumptions behind the recovery estimate.</p><p><a href="https://dbc-a3bbfca6-850a.cloud.databricks.com/genie/rooms/01f1db4548ec16ee9f10853bb4959656?o=7474653288963289">Ask the Pit Boss in Databricks Genie (workspace sign-in required)</a>.</p>';
}
function extra(name,title,rows) {
  if(name==="budget-allocation") return budgetAllocation();
  if(name==="unfunded-options") return unfundedOptions();
  if(name==="forecast-review") return forecastReview();
  if(name==="review-evidence") return staffingReview();
  const days = stable("floor").filter(r=>dateIn(r.gaming_date));
  const monthDays = new Map(groups(monthRows(days),["month"],{days:"count"}).map(r=>[r.month,r.days]));
  const cash = (key,label) => metric(key,label,currency);
  if(name==="monthly-demand") {
    const scoped = monthRows(rows);
    const byZone = groups(scoped,["month","zone_name"],{coin:"coin_in_usd",theo:"theo_usd"});
    const floor = groups(scoped,["month"],{coin:"coin_in_usd",theo:"theo_usd"}).map(r=>({...r,zone_name:filters.bank || filters.zone ? "Selected floor area" : "Entire floor"}));
    return table([metric("month","Month"),metric("zone_name","Zone"),cash("coin","Wagers per day"),cash("theo","Expected win per day")],
      [...floor,...byZone].sort((a,b)=>a.month.localeCompare(b.month)).map(r=>({...r,coin:r.coin/monthDays.get(r.month),theo:r.theo/monthDays.get(r.month)})));
  }
  if(name==="demand-bridge"){
    const totals = groups(monthRows(stable("demand_bridge").filter(r=>dateIn(r.gaming_date))),["month"],
      {days:"count",calendar:"calendar_usd",events:"event_usd",closure:"walkway_usd",other:"other_usd",actual:"actual_usd"});
    const daily=totals.sort((a,b)=>a.month.localeCompare(b.month))
      .map(r=>Object.fromEntries(Object.entries(r).map(([key,v])=>[key,key==="month"?v:v/r.days])));
    const cols=[metric("month","Month"),cash("calendar","Weekday mix"),cash("events","Events"),cash("closure","Closure"),
      cash("other","Other"),cash("actual","Actual wagers")];
    const first=daily[0], last=daily.at(-1);
    if (daily.length>1) daily.push({month:"Change from "+first.month+" to "+last.month,...Object.fromEntries(
      ["calendar","events","closure","other","actual"].map(key=>[key,last[key]-first[key]]))});
    return table(cols,daily);
  }
  if(name==="lasting-gap") return table([cash("jan_per_day","January per day"),cash("post_per_day","After closure per day"),
    cash("lasting_gap_usd_per_day","Difference per day"),cash("gap_relative_to_rest_usd_per_machine_day","Gap versus rest per machine-day")],stable("lasting_gap"));
  if(name==="high-limit") {
    const metrics = {top_visits_per_day:"Top-tenth visits per day",top_session_hours_per_day:"Top-tenth hours per day",
      other_tracked_hours_per_day:"Other tracked hours per day",occupied_hours_per_day:"Occupied hours per day",
      occupancy_pct:"Share of available time occupied (%)",coin_in_per_machine_day:"Wagers per machine-day ($)"};
    const chart = line("Top-tenth visits by gaming day",stable("high_limit_day").filter(r=>dateIn(r.gaming_date)),
      ["gaming_date","Gaming date"],[["top_visits","Top-tenth visits"]]);
    return chart+table([metric("metric","Measure"),metric("jan_apr","Jan–Apr"),metric("june","June"),metric("change_value","Change"),
      metric("ci90_lower","90% range, low"),metric("ci90_upper","90% range, high")],
      stable("high_limit_test").map(r=>({...r,metric:metrics[r.metric]})));
  }
  if(name==="downtime-total") return '<p class="big-number">'+usd.format(sum(rows,"leak_usd"))+'</p><p>'+fmt.format(sum(rows,"downtime_hours"))+' machine hours down.</p>';
  if(name==="downtime-month") return line(title,groups(monthRows(rows),["month"],{lost:"leak_usd"}),["month","Month"],[["lost","Expected win lost",currency]]);
  if(name==="downtime-maker") return table([metric("manufacturer","Manufacturer"),metric("hours","Hours down"),cash("lost","Expected win lost")],
    groups(rows,["manufacturer"],{hours:"downtime_hours",lost:"leak_usd"}).sort((a,b)=>b.lost-a.lost));
  if(name==="downtime-hour") {
    const zones=new Set(rows.map(r=>r.zone_id));
    const hours=groups(stable("downtime").filter(r=>dateIn(r.gaming_date)&&zones.has(r.zone_id)),["gaming_hour"],{lost:"lost_theo_usd"});
    if (!rows.length) return table([],[]);
    const hourValues=Array.from({length:24},(_,h)=>({hour:hourLabel(h),lost:hours.find(r=>r.gaming_hour===h)?.lost ?? 0}));
    return bars(title,hourValues,"hour","lost",currency);
  }
  if(name==="comp-weekly") {
    const rows=stable("comp_control_week");
    const fields=rows[0]||{};
    if (!("carded_coin_in" in fields)) return "";
    const before=rows.filter(r=>r.relative_week<0&&r.gaming_days===7);
    const carded=sum(before,"carded_coin_in")/before.length, uncarded=sum(before,"uncarded_coin_in")/before.length;
    return line(title,rows.filter(r=>r.gaming_days===7&&dateIn(r.week_start)&&dateIn(new Date(Date.parse(r.week_start)+6*86400000).toISOString().slice(0,10)))
      .map(r=>({...r,carded:r.carded_coin_in/carded,uncarded:r.uncarded_coin_in/uncarded})),["week_start","Week starting"],
      [["carded","Tracked",percent],["uncarded","Untracked",percent]],{shade:"2025-05-01"});
  }
  return "";
}

function planCards(rows) {
  const inspection = rows.find(row=>row.action_type_id==="A-INSPECT" && row.selected);
  const pilot = rows.find(row=>row.action_type_id==="A-COMP-PILOT");
  const move = rows.find(row=>row.action_type_id==="A-MOVE-BANK");
  const cards = [
    ["A","♥","Funded",inspection.cash_cost_usd,"Inspect "+inspection.target_id,
      "Check the payout meter, game settings, and accounting. Compare the records by "+inspection.measurement_date+". Confirm a repeatable discrepancy before approving more work."],
    ["K","♠","Deferred",pilot.cash_cost_usd,"Comp pilot",
      "The trial can only detect a change of 5.77% over 60 days. We need it to detect 2.5% before funding it."],
    ["Q","♦","Watchlist",move.cash_cost_usd,"Test the bank position",
      "Check whether the bank position explains the gap. A move does not pay for itself in July."],
    ["J","♣","Kept in reserve",data.cage[0].kept_usd,"Preserve the budget",
      "Keep the cash available and revisit the decision after the inspection and August results."]
  ];
  return '<p class="muted">Select a card to see the reasoning behind each decision.</p><div class="plan-cards">'
    +cards.map(([rank,suit,status,amount,title,reason])=>{
      const corner='<span class="plan-corner">'+rank+'<br>'+suit+'</span>';
      const label=title+', '+usd.format(amount);
      return '<button type="button" class="plan-card" aria-pressed="false" aria-label="'+escape(label)+'" data-front="'+escape(label)
        +'" data-back="'+escape(reason)+'"><span class="plan-face plan-front'+('♥♦'.includes(suit)?' red':'')+'" aria-hidden="true">'
        +corner+'<span class="plan-status">'+status+'</span><span class="plan-amount">'+usd.format(amount)
        +'</span><span class="plan-title">'+escape(title)+'</span>'+corner
        +'</span><span class="plan-face plan-back" aria-hidden="true"><span>'+escape(reason)+'</span></span></button>';
    }).join("")+'</div>';
}
function dealMachine() {
  const candidates=unique(stable("machine").filter(machineIn).map(row=>row.machine_id));
  const status=$("deal-status");
  if(!candidates.length){
    status.textContent="No machines match the selected filters.";
    return;
  }
  const id=candidates[Math.floor(Math.random()*candidates.length)];
  const row=stable("machine").find(machine=>machine.machine_id===id && machineIn(machine));
  const reel=$("lever").previousElementSibling;
  const labels=[id,Array.from(row.verdict_chip)[0],row.bank_name];
  reel.classList.remove("dealing");
  reel.querySelectorAll("span").forEach((item,i)=>item.textContent=labels[i]);
  void reel.offsetWidth;
  reel.classList.add("dealing");
  status.innerHTML='<button type="button" data-machine="'+escape(id)+'">Open '+escape(id)
    +'</button> '+escape(row.bank_name)+' · '+escape(row.verdict_chip);
}

function render() {
  const [slug, tab, title, description] = views[active];
  $("tabs").querySelectorAll("a").forEach((link,i)=>i===active?link.setAttribute("aria-current","page"):link.removeAttribute("aria-current"));
  for (const field of document.querySelectorAll(".guest")) field.hidden = !["players","comps"].includes(slug);
  const rows = stable("machine").filter(machineIn);
  const totals = kpis(rows,stable("floor").filter(r=>dateIn(r.gaming_date)));
  const scope = [selectedMachine,filters.start+" to "+filters.end,filters.zone,filters.bank,
    ...(["players","comps"].includes(slug)?[filters.tier,filters.region,filters.age]:[])].filter(Boolean).join(" · ");
  const intro = slug==="verdict" ? '<p>The longer comp trial could detect a smaller percentage change, 5.77% instead of 6.44%, even though the dollar change grew from $4.15 to $7.61. More expected win accumulates over 60 days.</p>'
    : slug==="luck" ? '<p>After accounting for the number of machines checked, a payout gap this large would occur by chance about 0.15% of the time. We put the chance of a fixable problem at 34% because a meter or accounting issue, a resolved fault, or a non-fixable cause could explain the gap.</p>'
    : slug==="demand" ? '<p>Las Vegas visitation from the LVCVA provides regional context. It does not enter the forecast or explain changes at this fictional property.</p>'
    : slug==="players" ? '<p>The six-month ranking and winner/loser split stay fixed. The tier and decile table uses the selected dates and guest group.</p>'
    : slug==="comps" ? '<p>Guest filters apply to redemption prices and the tracked reinvestment trend. The points balance and comparison with untracked wagers describe the whole floor.</p>'
    : "";
  const pip=["♠","♦","♣","♥","♠","♦","♥","♣","♠"][active];
  $("hero-host").innerHTML = slug==="verdict"?$("marquee-template").innerHTML:"";
  $("content").innerHTML = '<section class="intro"><p class="muted">'+escape(tab)+'</p><h2><span aria-hidden="true" class="pip'
    +("♥♦".includes(pip)?" red":"")+'">'+pip+'</span>'+escape(title)+'</h2><p>'+escape(description)
    +'</p><p class="muted" id="scope">'+escape(scope)+'</p>'+intro
    +(slug==="verdict"?pitBossAnswers():"")
    +(slug==="verdict" && insights.length?'<aside class="card strategic"><h3>What to do next</h3>'+insights.map(p=>'<p>'+escape(p)+'</p>').join("")+'</aside>':"")
    +'</section><div class="grid">'
    +layout[slug].map(name=>{
      if (!review && ["forecast-review","review-evidence"].includes(name)) return "";
      const widget = pages.get(name);
      const [heading,explanation] = copy[name] ?? extraCopy[name];
      let body, cls = "";
      if (!widget) {
        body=extra(name,heading,rows);
        cls=["monthly-demand","demand-bridge","high-limit","downtime-hour","budget-allocation","unfunded-options","forecast-review","review-evidence"].includes(name)?" wide":"";
      } else {
        const s = widget.spec, query = widget.queries[0].query;
        if (s.widgetType==="counter") {
          const value = totals[name] ?? ({spent:data.cage[0].spent_usd,kept:data.cage[0].kept_usd,"hold-ref":0})[name];
          const type = s.encodings.value.format?.type;
          const digits = type==="number-currency" ? 2 : 8;
          cls = " kpi";
          body = '<output data-kpi="'+name+'" data-value="'+(value==null?"":Number(value).toFixed(digits))+'">'+(value==null?"Unavailable":
            type==="number-currency"?usd.format(value):type==="number-percent"?pct.format(value):fmt.format(value))+'</output>';
        } else if (s.widgetType==="table") {
          let found = datasets[name] ? datasets[name](rows) : stable(query.datasetName);
          const order = query.orders?.[0]?.expression?.replaceAll(String.fromCharCode(96),"");
          if (order) found = [...found].sort((a,b)=>typeof a[order]==="number"?a[order]-b[order]:String(a[order]).localeCompare(b[order]));
          let cols = s.encodings.columns;
          if(name==="player-outcomes"){
            const tracked=found.filter(r=>r.outcome!=="No tracked gaming").reduce((n,r)=>n+r.players,0);
            found=found.map(r=>({...r,tracked_share:r.outcome==="No tracked gaming"?null:r.players/tracked}));
            cols=[...cols,metric("tracked_share","Share of players who wagered",percent)];
          }
          if(name==="player-segments") cols=cols.filter(c=>!["players","comp","contrib"].includes(c.fieldName))
            .map(c=>({...c,displayName:({theo:"Expected win",luck:"Player payout variation",wagers:"Wagers"})[c.fieldName]??c.displayName}));
          if(name==="cage-slip"){
            body=planCards(found)+table(cols.filter(c=>!["assumption","success_rule","evidence_view"].includes(c.fieldName)),found);
          } else {
            body=table(cols,found);
            if(name==="comp-control"){
              const pre=stable("comp_control_pretrend")[0];
              body+='<p class="muted">Before May 1, the tracked share changed by '+fmt.format(pre.share_pp_slope)
                +' percentage points per week across '+fmt.format(pre.weeks)+' complete weeks. That check helps assess whether the groups were already moving apart.</p>';
            }
          }
          cls = cols.length>=5 && name!=="tribunal" ? " wide" : "";
        } else if (s.widgetType==="line") body=compTrend(name,heading);
        else {
          body=charts(name,heading,rows);
          cls = ["slot-map","action-board","model-holdout","demand-timeline"].includes(name) ? " wide" : "";
        }
      }
      const scoped = name==="tribunal" && (filters.zone || filters.bank || selectedMachine);
      return '<section class="card'+cls+'" id="'+name+'"><h3>'+escape(scoped?"Machines in the selected area":heading)
        +'</h3><p class="muted">'+escape(scoped?"The table shows up to ten machines, ordered by their six-month rank.":explanation)+'</p>'+body+'</section>';
    }).join("")+'</div>';
  $("content").setAttribute("aria-busy","false");
}
function currentView() {
  const alias = {"pit-boss":"verdict","luck-funnel":"luck","floor-radar":"demand","high-roller":"players","cashier":"plan","model-room":"model","evidence-vault":"evidence"};
  const hash = location.hash.replace(/^#\/?/,"");
  return Math.max(0,views.findIndex(([slug])=>slug===(alias[hash] || hash)));
}
function route() {
  active=currentView();
  render();
  scrollTo(0,0);
  if (evidenceMachine && views[active][0]==="evidence") $("evidence-match")?.scrollIntoView({block:"center"});
}
function go(slug) {
  if (location.hash==="#/"+slug) route();
  else location.hash="/"+slug;
}
function options(id, values) {
  const select = $(id), current = select.value;
  select.replaceChildren(select.options[0], ...values.map(v=>new Option(v,v)));
  if (values.includes(current)) select.value=current;
}
function banks() {
  options("bank",unique(stable("machine").filter(r=>!$("zone").value || r.zone_name===$("zone").value).map(r=>r.bank_name)));
}
function drawer(machine, date) {
  const days = stable("machine").filter(r=>r.machine_id===machine && dateIn(r.gaming_date)).sort((a,b)=>b.gaming_date.localeCompare(a.gaming_date));
  const downtime = stable("timeline").filter(r=>r.machine_id===machine);
  date ||= days.find(r=>downtime.some(t=>t.gaming_date===r.gaming_date))?.gaming_date ?? days[0]?.gaming_date;
  const day = days.find(r=>r.gaming_date===date);
  const hours = new Map((downtime.find(r=>r.gaming_date===date)?.hours ?? []).map(h=>[h.h,h]));
  const slots = Array.from({length:24},(_,h)=>h).filter(h=>date!=="2025-03-08" || h!==20);
  $("detail").innerHTML = '<h2 id="machine-title">'+escape(machine)+'</h2>'
    + (day ? '<p>'+escape(day.bank_name)+' · <span class="chip" style="color:'+suitColor(day.verdict_chip)+'">'+escape(day.verdict_chip)
      +'</span></p><label>Gaming date <select id="machine-day">'+days.map(r=>'<option'+(r.gaming_date===date?' selected':'')+'>'+r.gaming_date+'</option>').join("")
      +'</select></label><h3>Gaming-day timeline · 06:00 → 06:00</h3><p class="muted">Las Vegas local time. Each cell shows reported available time. A gaming day with a spring clock change has 23 hours.</p>'
      +'<div class="timeline">'+slots.map(h=>'<div class="hour'+(hours.get(h)?.d>0?' down':'')+'"><strong>'+hourLabel(h)+'</strong><br>'
        +fmt.format((hours.get(h)?.a ?? 1)*60)+'m'+(hours.get(h)?.d>0?'<br>Down '+fmt.format(hours.get(h).d*60)+'m':'')+'</div>').join("")
      +'</div><p>Coin-in '+usd.format(day.coin_in_usd)+' · Theo '+usd.format(day.theo_usd)+' · Actual '+usd.format(day.house_win_usd)
      +'</p><button data-focus-machine="'+escape(machine)+'">Show how this machine reached actual win</button>' : '<p>No machine data in this date range.</p>');
  if (day) $("machine-day").addEventListener("change",e=>{drawer(machine,e.target.value);$("machine-day").focus();});
  if (!$("drawer").open) $("drawer").showModal();
}
async function start() {
  const response=await fetch("./gold.json");
  if (!response.ok) throw new Error("The Gold export is unavailable.");
  const result=await response.json();
  review=result.review;
  insights=result.insights || [];
  pages=new Map(result.pages.flatMap(p=>p.layout).map(({widget})=>[widget.name,widget]));
  data = Object.fromEntries(Object.entries(result.datasets).map(([key,{columns,rows}])=>
    [key,rows.map(row=>Object.fromEntries(columns.map((column,i)=>[column,row[i]])))]));
  $("provenance").textContent = "All figures come from the Gilded Ace Databricks pipeline (gold tables), exported "
    + stable("export_metadata")[0].exported_on + ".";
  $("tabs").innerHTML = views.map(([slug,tab])=>'<a href="#/'+slug+'">'+escape(tab)+'</a>').join("");
  options("zone",unique(stable("machine").map(r=>r.zone_name)));
  options("tier",unique(stable("segments").map(r=>r.tier_end)));
  options("region",unique(stable("segments").map(r=>r.home_region)));
  options("age",unique(stable("segments").map(r=>r.age_band)));
  banks();
  $("zone").addEventListener("change",banks);
  $("filters").addEventListener("submit",event=>{
    event.preventDefault();
    $("end").setCustomValidity($("start").value > $("end").value ? "End date must be on or after the start date." : "");
    if (!$("filters").reportValidity()) return;
    for(const key of Object.keys(filters)) filters[key]=$(key).value;
    selectedMachine="";
    playSound("chips");
    render();
  });
  $("end").addEventListener("input",()=>$("end").setCustomValidity(""));
  $("start").addEventListener("input",()=>$("end").setCustomValidity(""));
  $("filters").addEventListener("reset",()=>setTimeout(()=>{
    $("end").setCustomValidity("");banks();$("filters").requestSubmit();
  }));
  $("dismiss").addEventListener("click",()=>$("drawer").close());
  history.scrollRestoration="manual";
  window.addEventListener("hashchange",route);
  document.addEventListener("click",event=>{
    const target=event.target.closest("[data-machine],[data-evidence],[data-focus-machine],.plan-card,#lever");
    if (!target) return;
    if (target.id==="lever") { playSound("lever"); dealMachine(); }
    if (target.matches(".plan-card")) {
      const flipped=target.getAttribute("aria-pressed")==="true";
      target.setAttribute("aria-pressed",String(!flipped));
      target.setAttribute("aria-label",flipped?target.dataset.front:target.dataset.back);
      playSound("card");
    }
    if (target.dataset.machine) drawer(target.dataset.machine);
    if (target.dataset.focusMachine) { selectedMachine=target.dataset.focusMachine;$("drawer").close();go("verdict"); }
    if (target.dataset.evidence) { evidenceMachine=target.dataset.evidence;go("evidence"); }
  });
  document.addEventListener("keydown",event=>{
    if (event.target.matches("circle[data-machine]") && ["Enter"," "].includes(event.key)) {
      event.preventDefault();drawer(event.target.dataset.machine);
    }
  });
  setupAudio();
  route();
}
start().catch(error=>{
  $("content").textContent="The Gold snapshot could not be opened in this browser.";
  $("content").setAttribute("aria-busy","false");
  console.error(error);
});

// The short envelopes and the loop are synthesized in the browser.
let audioContext, musicSource;
function audio() {
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (!Audio) return null;
  audioContext ||= new Audio();
  if (audioContext.state === "suspended") audioContext.resume().catch(()=>{});
  return audioContext;
}
function playSound(effect) {
  if (!$("sound").checked) return;
  const ctx=audio();
  if (!ctx) return;
  const start=ctx.currentTime;
  const tones={chips:[1260,1680,2120],lever:[150,92],card:[470,650]}[effect];
  for (const [i,freq] of tones.entries()) {
    const t=start+i*.028, oscillator=ctx.createOscillator(), volume=ctx.createGain();
    oscillator.type=effect==="lever"?"triangle":"sine";
    oscillator.frequency.setValueAtTime(freq,t);
    oscillator.frequency.exponentialRampToValueAtTime(freq*.58,t+.11);
    volume.gain.setValueAtTime(.0001,t);
    volume.gain.exponentialRampToValueAtTime(.04,t+.008);
    volume.gain.exponentialRampToValueAtTime(.0001,t+.13);
    oscillator.connect(volume).connect(ctx.destination);
    oscillator.start(t);oscillator.stop(t+.14);
  }
}
function startMusic() {
  if (musicSource || !$("music").checked) return;
  const ctx=audio();
  if (!ctx) return;
  const buffer=ctx.createBuffer(1,8*ctx.sampleRate,ctx.sampleRate);
  const track=buffer.getChannelData(0);
  for(let i=0;i<track.length;i++){
    const t=i/ctx.sampleRate, phase=t*2*Math.PI;
    const pulse=.53+.47*Math.cos(phase/8);
    track[i]=.008*pulse*(Math.sin(phase*55)+.4*Math.sin(phase*82.5)+.28*Math.sin(phase*110));
  }
  musicSource=ctx.createBufferSource();
  musicSource.buffer=buffer;musicSource.loop=true;musicSource.connect(ctx.destination);musicSource.start();
}
function setupAudio() {
  for(const key of ["sound","music"]){
    const control=$(key);
    try { control.checked=localStorage.getItem("ace-"+key)==="on"; } catch {}
    control.addEventListener("change",()=>{
      try { localStorage.setItem("ace-"+key,control.checked?"on":"off"); } catch {}
      if(key==="music"){
        if(control.checked) startMusic();
        else if(musicSource){musicSource.stop();musicSource=null;}
      } else if(control.checked) playSound("chips");
    });
  }
  // Chrome and Safari require a user gesture even when a saved choice is on.
  document.addEventListener("pointerdown",startMusic,{once:true});
  document.addEventListener("keydown",startMusic,{once:true});
}
