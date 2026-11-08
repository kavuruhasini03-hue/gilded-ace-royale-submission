"""Generate the governed Lakeview dashboard and optionally validate its SQL."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "workspace.royale."
OUT = Path(__file__).with_name("gilded_ace.lvdash.json")
GOLD, CANVAS, BAIZE, SEAM, IVORY, SMOKE = "#D4AF37", "#0B0F0D", "#10241B", "#24443A", "#EDE6D3", "#9FAEA6"
PEWTER, PURPLE, CYAN, CORAL, BRASS, BONE, JADE = "#8A9690", "#B48CFF", "#3FD6E0", "#FF5A6E", "#C9A66B", "#F4F1EA", "#38D39F"
SUITS = {"♦ LUCK": PURPLE, "♣ LOCATION": CYAN, "♥ LEAK": CORAL, "⚙ LINEUP": BRASS,
         "♠ REPLACE (long-term candidate)": BONE, "🔍 INSPECT": GOLD}
VERDICT = ("Replace none of the GM’s bottom ten in July, inspect M-1158, defer the underpowered comp pilot, "
           "and keep $98,800 in reserve.")
MONEY = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact"}
PERCENT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 2}}


def field(name, expression=None):
    return {"name": name, "expression": expression or f"`{name}`"}


def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def text(name, markdown, y=0, h=2):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [markdown]}}, "position": pos(0, y, 12, h)}


def frame(title, description):
    return {"title": title, "showTitle": True, "description": description, "showDescription": True}


def query(dataset, fields, raw, order=None):
    q = {"datasetName": dataset, "fields": fields, "disaggregated": raw}
    if order:
        q["orders"] = [{"direction": "ASC", "expression": order}]
    return {"name": "main_query", "query": q}


def viz(name, dataset, fields, spec, title, description, placement, raw=False, order=None):
    return {"widget": {"name": name, "queries": [query(dataset, fields, raw, order)],
                       "spec": {**spec, "frame": frame(title, description)}}, "position": placement}


def column(name, label, fmt=None):
    value = {"fieldName": name, "displayName": label}
    if fmt:
        value["format"] = fmt
    return value


def table(name, dataset, cols, title, description, placement, raw=True, order=None):
    fields = [field(c[0], c[2] if len(c) > 2 else None) for c in cols]
    columns = [column(c[0], c[1], c[3] if len(c) > 3 else None) for c in cols]
    return viz(name, dataset, fields, {"version": 2, "widgetType": "table", "encodings": {"columns": columns}},
               title, description, placement, raw, order)


def counter(name, dataset, expression, title, description, placement, fmt=MONEY):
    return viz(name, dataset, [field("value", expression)],
               {"version": 2, "widgetType": "counter", "encodings": {"value": column("value", title, fmt)}},
               title, description, placement)


def axis(name, kind, title=None, **extras):
    return {"field": name, "type": kind, **({"title": title} if title is not None else {}), **extras}


def custom(name, dataset, fields, body, title, description, placement, raw=True):
    inner = {"$schema": "https://vega.github.io/schema/vega-lite/v6.json", "data": {"name": "databricks_query"},
             "width": "container", "height": "container", "background": "transparent",
             "config": {"autosize": {"type": "fit", "contains": "padding"}, "view": {"stroke": None},
                        "axis": {"labelColor": SMOKE, "titleColor": IVORY, "gridColor": SEAM, "domainColor": SEAM},
                        "legend": {"labelColor": IVORY, "titleColor": IVORY}}, **body}
    spec = {"version": 1, "widgetType": "custom-vega-viz", "data": {"queryName": "main_query"},
            "encodings": {"fields": [{"fieldName": f["name"]} for f in fields]},
            "jsonSpec": {"type": "vega-lite", "spec": json.dumps(inner, ensure_ascii=False, separators=(",", ":"))}}
    return viz(name, dataset, fields, spec, title, description, placement, raw)


def page(name, label, *layout, global_filters=False):
    return {"name": name, "displayName": label, "layout": list(layout), "layoutVersion": "GRID_V1",
            "pageType": "PAGE_TYPE_GLOBAL_FILTERS" if global_filters else "PAGE_TYPE_CANVAS"}


def simple_line(name, dataset, date_field, values, title, description, placement, fmt=None):
    fields = [field(date_field), *(field(key) for key, _ in values)]
    date = {"fieldName": date_field, "scale": {"type": "temporal"}}
    y = {"scale": {"type": "quantitative"}, "fields": [column(k, label, fmt) for k, label in values]}
    return viz(name, dataset, fields, {"version": 3, "widgetType": "line", "encodings": {"x": date, "y": y}},
               title, description, placement, True, f"`{date_field}`")


def filter_widget(name, label, kind, bindings, x, y, width, default=None):
    queries = []
    encodings = []
    for ds, key in bindings:
        q = query(ds, [field(key)], False)
        q["name"] = f"{ds}_{key}"
        queries.append(q)
        encodings.append({"fieldName": key, "displayName": label, "queryName": q["name"]})
    spec = {"version": 2, "widgetType": kind, "encodings": {"fields": encodings},
            "frame": {"title": label, "showTitle": True}}
    if default:
        spec["selection"] = {"defaultSelection": default}
    return {"widget": {"name": name, "queries": queries, "spec": spec}, "position": pos(x, y, width, 2)}


def source(view):
    return f"SELECT * FROM {SCHEMA}{view}"


def datasets():
    return {
        "machine": f"""SELECT d.*, v.verdict_chip, v.gm_rank, v.adjusted_rank, v.last_zone, v.last_bank_name
            FROM {SCHEMA}gold_machine_day d JOIN {SCHEMA}gold_machine_verdict v USING (machine_id)""",
        "adjusted": source("gold_adjusted_bottom10"),
        "comparison": f"""SELECT machine_id, theo_usd, house_win_usd, verdict_chip, gm_rank, adjusted_rank
            FROM {SCHEMA}gold_machine_verdict WHERE gm_rank<=10 OR adjusted_rank<=10""",
        "rank": f"{source('gold_bottom10_mean_reversion')} WHERE gm_rank<=10",
        "floor": source("gold_kpi_header"),
        "traffic": f"""SELECT *, CASE zone_id
            WHEN 'Z-B40' THEN 'Back Forty' WHEN 'Z-BAR' THEN 'Bar Row' WHEN 'Z-ENT' THEN 'Main Entrance'
            WHEN 'Z-GAR' THEN 'Garage Entrance' WHEN 'Z-HL' THEN 'High-Limit Room'
            WHEN 'Z-HTL' THEN 'Hotel Corridor' WHEN 'Z-PIT' THEN 'Center Pit' END AS zone_name
            FROM {SCHEMA}gold_zone_gaming_hour""",
        "walkway": f"""SELECT *, CASE phase WHEN 'pre' THEN '1 Before' WHEN 'closure' THEN '2 Closed'
            ELSE '3 After' END AS period FROM {SCHEMA}gold_walkway_did""",
        "demand": f"""SELECT d.*, f.forecast_usd, f.split FROM {SCHEMA}gold_demand_context_day d
            JOIN {SCHEMA}gold_forecast_day f USING (gaming_date)""",
        "zones": source("gold_zone_other_bridge"),
        "fault": f"{source('gold_downtime_ticket')} WHERE event_type='fault_repair'",
        "concentration": source("gold_concentration"),
        "ladder": f"""SELECT player_rank,cumulative_player_share,cumulative_theo_share,cumulative_coin_in_share
            FROM {SCHEMA}gold_lorenz WHERE PMOD(player_rank,400)=0 OR player_rank IN (1,1138,11389,113890)""",
        "segments": f"""SELECT *, TO_DATE(CONCAT(period_month,'-01')) AS gaming_date
            FROM {SCHEMA}gold_player_decile_month""",
        "outcomes": source("gold_player_outcome_split"),
        "hist": f"""SELECT bin_id, CASE bin_id WHEN 0 THEN '0 No tracked gaming' WHEN 1 THEN '1 Below −$1,000'
            WHEN 2 THEN '2 −$1,000 to −$100' WHEN 3 THEN '3 Loss under $100' WHEN 4 THEN '4 Exactly zero'
            WHEN 5 THEN '5 Win up to $100' WHEN 6 THEN '6 $100 to $1,000' ELSE '7 Above $1,000' END AS band,
            observations, player_net_usd FROM {SCHEMA}gold_player_net_histogram WHERE period='Jan–Jun'""",
        "comps": f"SELECT *, valuation_date AS gaming_date FROM {SCHEMA}gold_comp_week",
        "control": source("gold_comp_control_effect"),
        "points": source("gold_points_liability_bridge"),
        "actions": f"""{source('gold_action_plan')} WHERE horizon_days=30""",
        "annual": f"""{source('gold_action_plan')} WHERE horizon_days=365""",
        "tech_sensitivity": f"""{source('gold_action_plan')} WHERE horizon_days=30 AND action_type_id IN ('A-TECH-SHIFT','A-PREVENTIVE')""",
        "cage": source("gold_cage_slip"),
        "tech": f"""{source('gold_tech_shift_economics')} WHERE horizon_days=30""",
        "forecast": source("gold_forecast_day"),
        "scores": source("gold_forecast_holdout_metrics"),
        "residual": source("gold_forecast_weekday_residual"),
        "evidence": source("gold_claims_evidence"),
    }


def board():
    return [
        text("verdict", f"## {VERDICT}\n\n**THE GILDED ACE · EYE IN THE SKY** · Fictional casino · Jan–Jun 2025 evidence\n\n**Comp monitoring:** review comp pricing and tracked play if cost exceeds 1.50% of tracked theo for two consecutive complete gaming weeks.\n\n**Pilot power:** the 60-day MDE is larger in dollars ($7.61 vs $4.15) but smaller as a share (5.77% vs 6.44%) because the baseline contribution accumulates over more days.\n\n[Ask the Pit Boss in Genie (workspace sign-in required)](https://dbc-a3bbfca6-850a.cloud.databricks.com/genie/rooms/01f1db4548ec16ee9f10853bb4959656?o=7474653288963289).", h=5),
        counter("health", "machine", "SUM(theo_usd)/NULLIF(SUM(theo_usd + leak_usd + location_opportunity_usd),0)",
                "Theo captured", "Health versus the best observed zone factor after leak.", pos(0, 5, 2, 3), PERCENT),
        counter("coin", "machine", "SUM(coin_in_usd)", "Coin-in", "Total wagers in the current slice.", pos(2, 5, 2, 3)),
        counter("hold", "machine", "SUM(house_win_usd)/NULLIF(SUM(coin_in_usd),0)", "Actual hold",
                "House win divided by wagers.", pos(4, 5, 2, 3), PERCENT),
        counter("theo-hold", "machine", "SUM(theo_usd)/NULLIF(SUM(coin_in_usd),0)", "Theo hold",
                "Expected win divided by wagers.", pos(6, 5, 2, 3), PERCENT),
        counter("luck", "machine", "SUM(luck_residual_usd)", "Luck residual", "Actual win less expected win.", pos(8, 5, 2, 3)),
        counter("leak", "machine", "SUM(leak_usd)", "Theo lost to downtime", "Hour-weighted opportunity.", pos(10, 5, 2, 3)),
        counter("comp-kpi", "floor", "SUM(comp_cost_usd)/NULLIF(SUM(tracked_theo_usd),0)",
                "Comp reinvestment", "Tracked theo denominator. Floor-wide, date filter only.", pos(0, 8, 4, 3), PERCENT),
        counter("sigma-kpi", "machine", "SUM(luck_residual_usd)/NULLIF(SQRT(SUM(luck_variance_usd2)),0)",
                "Luck z-score", "A magnitude under 2 is within the two-sigma screen.", pos(4, 8, 4, 3), None),
        counter("cash-kept", "cage", "MAX(kept_usd)", "Kept in the cage", "July plan is a fixed decision snapshot.", pos(8, 8, 4, 3)),
        table("tribunal", "machine", [("machine_id","Machine"),("gm_rank","GM rank"),("last_bank_name","Last bank"),
                    ("verdict_chip","Verdict"),("win","Win in slice","SUM(house_win_usd)",MONEY)],
              "The GM’s raw list starts with exposure and lineup", "Select a machine row to focus the shared bridge. Rank is Jan–Jun.",
              pos(0, 11, 6, 7), False, "`gm_rank`"),
        bridge(),
        table("adjusted", "adjusted", [("adjusted_rank","Rank"),("machine_id","Machine"),("last_bank_name","Bank"),
              ("verdict_chip","Verdict"),("floor_days","Floor days"),("net_benefit_12m_usd","12-month net",None,MONEY),
              ("payback_month","Payback month")], "The adjusted list identifies three long-term candidates",
              "Full-window ranks and lease economics. None clears the July screen.", pos(0, 18, 12, 6), order="`adjusted_rank`"),
        table("cage-overview","cage",[("spent_usd","Funded",None,MONEY),("kept_usd","Kept",None,MONEY),
              ("funded_action_types","Funded types")],"One inspection, no July replacements",
              "See the Evidence Vault for assumptions and alternative explanations.",pos(0, 24,12,3))
    ]


def bridge():
    keys = ["Potential", "♥ LEAK", "♣ LOCATION", "⚙ LINEUP", "♠ Machine-specific", "Theo", "♦ LUCK", "Actual"]
    names = ["potential", "leak", "location", "lineup", "machine_effect", "theo", "luck", "actual"]
    exprs = ["potential_theo_usd", "-leak_usd", "location_usd", "lineup_usd", "machine_specific_usd",
             "theo_usd", "luck_residual_usd", "house_win_usd"]
    label = dict(zip(names,keys))
    transform = [{"fold": names, "as": ["step","amount"]},
                 {"calculate": f"indexof({json.dumps(names)}, datum.step)", "as": "idx"},
                 {"calculate": "datum.step === 'theo' || datum.step === 'actual' ? 0 : datum.amount", "as": "delta"},
                 {"window": [{"op":"sum","field":"delta","as":"running"}], "sort":[{"field":"idx"}]},
                 {"calculate":"datum.step === 'theo' || datum.step === 'actual' ? 0 : datum.running-datum.delta","as":"start"},
                 {"calculate":"datum.step === 'theo' || datum.step === 'actual' ? datum.amount : datum.running","as":"end"},
                 {"calculate": f"{json.dumps(keys,ensure_ascii=False)}[datum.idx]", "as":"label"}]
    return custom("bridge","machine",[field(k,f"SUM({v})") for k,v in zip(names,exprs)],{
        "transform":transform,"mark":{"type":"bar","cornerRadius":2},
        "encoding":{"y":axis("label","ordinal",sort=list(label.values())),
                    "x":axis("start","quantitative","USD",axis={"format":"$~s"}),"x2":{"field":"end"},
                    "color":axis("label","nominal",scale={"domain":keys,"range":[PEWTER,CORAL,CYAN,BRASS,BONE,PEWTER,PURPLE,JADE]},legend=None),
                    "tooltip":[axis("label","nominal","Component"),axis("amount","quantitative","USD",format="$,.0f")]}
    },"The 4-L bridge closes to actual win","Start at potential, subtract leak, add signed drivers and then luck.",pos(6,11,6,7),False)


def suit(field_name="verdict_chip"):
    return axis(field_name, "nominal", "Verdict",
                scale={"domain": list(SUITS), "range": list(SUITS.values())})


def luck_page():
    xf = axis("sigma", "quantitative", "Expected sigma ($)", axis={"format":"$~s"})
    yf = axis("luck", "quantitative", "Luck residual ($)", axis={"format":"$~s"})
    funnel = custom("luck-funnel", "machine", [field("machine_id"), field("verdict_chip"), field("gm_rank"),
                field("sigma","SQRT(SUM(luck_variance_usd2))"), field("luck","SUM(luck_residual_usd)"),
                field("hours","SUM(available_hours)")], {
        "layer": [
            {"transform":[{"calculate":"[-3,-2,2,3]","as":"bounds"},{"flatten":["bounds"],"as":["k"]},
                          {"calculate":"datum.k*datum.sigma","as":"bound_usd"}],
             "mark":{"type":"line","color":PEWTER,"opacity":0.65},
             "encoding":{"x":xf,"y":{**yf,"field":"bound_usd"},"detail":axis("k","nominal"),
                         "strokeDash":axis("k","nominal",legend=None)}},
            {"mark":{"type":"point","filled":True,"opacity":0.78},
             "encoding":{"x":xf,"y":yf,"color":suit(),"size":axis("hours","quantitative","Available hours",legend=None),
                         "stroke":{"condition":{"test":"datum.gm_rank <= 10","value":GOLD},"value":None},
                         "tooltip":[axis("machine_id","nominal","Machine"),axis("verdict_chip","nominal","Verdict"),
                                    axis("sigma","quantitative","Sigma",format="$,.0f"),axis("luck","quantitative","Luck",format="$,.0f")]}}
        ]},"M-1158 warrants a payout check","Luck alone is unlikely (adjusted p = 0.0015), but only 34% is modeled as real and fixable because meter or accounting effects, resolved issues and non-fixable causes remain possible.",
        pos(0,2,12,8),False)
    versus = custom("actual-theo","comparison",[field(k) for k in ("machine_id","theo_usd","house_win_usd","verdict_chip")],{
        "layer":[
            {"mark":{"type":"rule","color":PEWTER},"encoding":{"y":axis("machine_id","nominal","Machine"),
                 "x":axis("theo_usd","quantitative","Win ($)"),"x2":{"field":"house_win_usd"}}},
            {"mark":{"type":"point","filled":True,"color":PEWTER},"encoding":{"y":axis("machine_id","nominal"),
                 "x":axis("theo_usd","quantitative")}},
            {"mark":{"type":"point","filled":True},"encoding":{"y":axis("machine_id","nominal"),
                 "x":axis("house_win_usd","quantitative"),"color":{**suit(),"legend":None}}}
        ]},"Actual win can miss theo by a wide margin","Pewter is theo. The colored end is actual win.",pos(0,10,6,10))
    ranking = table("mean-reversion","rank",[("machine_id","Machine"),("jan_mar_rank","Jan–Mar rank"),
                     ("apr_jun_rank","Apr–Jun rank"),("luck_z","Luck z")],
                    "Raw bottom ranks move unevenly","Three of eight machines ranked in both halves improved.",
                    pos(6,10,6,5),order="`gm_rank`")
    peers = custom("peers","machine",[field("config_id"),field("machine_id"),
                   field("rate","SUM(theo_usd)/NULLIF(SUM(available_hours),0)"),field("verdict_chip")],{
        "mark":{"type":"point","filled":True,"opacity":0.63},
        "encoding":{"x":axis("rate","quantitative","Theo per available hour",axis={"format":"$~s"}),
                    "y":axis("config_id","nominal","Config"),"color":{**suit(),"legend":None},
                    "tooltip":[axis("machine_id","nominal"),axis("rate","quantitative",format="$.2f")]}
    },"Game settings shift the peer baseline","Compare machines within their installed configuration.",pos(6,15,6,5),False)
    return page("luck-funnel","Luck Funnel",text("luck-intro","## THE LUCK FUNNEL\n\nSeparate meter variation from a repeatable performance gap."),funnel,versus,ranking,peers)


def floor_page():
    floor_map = custom("slot-map","machine",[field(k) for k in ("machine_id","x_m","y_m","bank_name","verdict_chip")]
                       +[field("rate","SUM(theo_usd)/NULLIF(SUM(available_hours),0)")],{
        "layer":[
            {"mark":{"type":"point","filled":True,"opacity":0.8},
             "encoding":{"x":axis("x_m","quantitative","Floor x (m)",scale={"zero":False}),
                         "y":axis("y_m","quantitative","Floor y (m)",scale={"zero":False}),
                         "color":suit(),"size":axis("rate","quantitative","Theo/hour",legend=None),
                         "tooltip":[axis(k,"nominal") for k in ("machine_id","bank_name","verdict_chip")]}},
            {"data":{"values":[{"x":15,"y":50,"x2":20,"y2":92}]},
             "mark":{"type":"rule","color":CYAN,"strokeDash":[5,4],"strokeWidth":2},
             "encoding":{"x":axis("x","quantitative",scale={"zero":False}),"x2":{"field":"x2"},
                         "y":axis("y","quantitative",scale={"zero":False}),"y2":{"field":"y2"}}},
            {"data":{"values":[{"x":20,"y":92,"zone":"Back Forty"},{"x":100,"y":72,"zone":"Bar Row"},
                 {"x":15,"y":50,"zone":"Main Entrance"},{"x":120,"y":100,"zone":"Garage Entrance"},
                 {"x":105,"y":22,"zone":"High-Limit"},{"x":62,"y":8,"zone":"Hotel Corridor"},
                 {"x":60,"y":50,"zone":"Center Pit"}]},
             "mark":{"type":"text","color":IVORY,"fontWeight":600,"dy":-8},
             "encoding":{"x":axis("x","quantitative",scale={"zero":False}),
                         "y":axis("y","quantitative",scale={"zero":False}),"text":{"field":"zone"}}}
        ]
    },"Bank positions reveal local clusters","Dots are observed slot positions. The dashed route was closed Mar 3–Apr 7.",pos(0,2,7,8),False)
    def heat(name, expr, title, description, placement, color):
        return custom(name,"traffic",[field("zone_id"),field("gaming_hour"),field("metric",expr)],{
            "mark":"rect","encoding":{"x":axis("gaming_hour","ordinal","Gaming hour from 06:00"),
                "y":axis("zone_id","nominal","Zone"),
                "color":axis("metric","quantitative",scale={"range":[BAIZE,color]}),
                "tooltip":[axis("zone_id","nominal"),axis("gaming_hour","ordinal"),axis("metric","quantitative",format=",.1f")]}
        },title,description,placement,False)
    traffic=heat("traffic-heat","60*SUM(entries)/NULLIF(SUM(coverage_minutes),0)","Counters peak at different hours",
                 "Crossings per covered sensor-hour. Blanks indicate no coverage.",pos(7,2,5,4),CYAN)
    leak=heat("leak-heat","SUM(lost_theo_usd)","Downtime costs most at busy hours",
              "Estimated lost theo weights unavailable time by hour.",pos(7,6,5,4),CORAL)
    timeline = timeline_chart("demand-timeline","demand","coin_in_usd",["forecast_usd"],"Back Forty weakened during the closure",
                              "Actual coin-in and the frozen forecast. Shaded days overlap the walkway closure.",pos(0,10,12,7),
                              "2025-03-03","2025-04-07",["Forecast"])
    compare = custom("walkway-did","walkway",[field(k) for k in ("period","back_forty_index","control_index")],{
        "transform":[{"fold":["back_forty_index","control_index"],"as":["series","value"]},
                     {"calculate":"datum.series === 'back_forty_index' ? 'Back Forty' : 'Rest of floor'","as":"group"}],
        "mark":{"type":"line","point":True},"encoding":{"x":axis("period","ordinal","Walkway phase"),
            "y":axis("value","quantitative","Pre = 100",scale={"zero":False}),
            "color":axis("group","nominal",scale={"domain":["Back Forty","Rest of floor"],"range":[CYAN,PEWTER]})}
    },"Back Forty fell to 71 while controls reached 103","Coin-in per installed machine-day. The pre-trend limits causal attribution.",pos(0,17,6,5))
    faults = custom("fault-hour","fault",[field("gaming_hour"),field("wait","AVG(wait_seconds)/3600.0"),
                                       field("work","AVG(work_seconds)/3600.0")],{
        "transform":[{"fold":["wait","work"],"as":["part","hours"]}],
        "mark":"bar","encoding":{"x":axis("gaming_hour","ordinal","Gaming hour from 06:00"),
           "y":axis("hours","quantitative","Mean hours"),"color":axis("part","nominal",scale={"range":[CORAL,PEWTER]})}
    },"Wait and repair time are different costs","Mean wait plus work time for fault tickets by opening hour.",pos(6,17,6,5),False)
    downtime = custom("leak-month","machine",[field("month","DATE_TRUNC('month',gaming_date)"),field("manufacturer"),
                                            field("downtime","SUM(downtime_hours)")],{
        "mark":"bar","encoding":{"x":axis("month","temporal","Month",timeUnit="yearmonth"),
             "y":axis("downtime","quantitative","Downtime hours"),"color":axis("manufacturer","nominal",
              scale={"range":[PEWTER,BRASS,CORAL]})}
    },"Ridgeline accounts for the largest six-month leak","Hours are stacked by manufacturer, with date and floor filters applied.",pos(0,22,6,5),False)
    zones = table("zone-drivers","zones",[("zone_name","Zone"),("other_change_usd_per_day","Other / day",None,MONEY),
                  ("occupied_hours_effect_usd_per_day","Hours",None,MONEY),("bet_effect_usd_per_day","Bet",None,MONEY),
                  ("spins_per_hour_effect_usd_per_day","Pace",None,MONEY)],"Occupied time explains most of the residual",
                  "January–June standardized bridge. The Back Forty lasting gap is descriptive.",pos(6,22,6,5))
    return page("floor-radar","Floor Radar",text("floor-intro","## THE FLOOR RADAR\n\nFollow foot traffic, floor demand and the cost of unavailable machines."),
                floor_map,traffic,leak,timeline,compare,faults,downtime,zones)


def timeline_chart(name, dataset, actual, prediction, title, desc, placement, shade_start, shade_end, labels):
    fields=[actual,*prediction]
    display=dict(zip(fields,["Actual",*labels]))
    legend=list(display.values())
    layer=[
        {"data":{"values":[{"start":shade_start,"end":shade_end}]},
         "mark":{"type":"rect","color":GOLD,"opacity":0.10},
         "encoding":{"x":axis("start","temporal","Gaming date"),"x2":{"field":"end"}}},
        {"transform":[{"fold":fields,"as":["series","coin"]},
                      {"calculate":f"{json.dumps(legend,ensure_ascii=False)}[indexof({json.dumps(fields)}, datum.series)]","as":"label"}],
         "mark":{"type":"line","strokeWidth":1.6},
         "encoding":{"x":axis("gaming_date","temporal","Gaming date"),
                     "y":axis("coin","quantitative","Daily coin-in",axis={"format":"$~s"},scale={"zero":False}),
                     "color":axis("label","nominal",scale={"domain":legend,"range":[IVORY,CYAN,PEWTER][:len(legend)]}),
                     "tooltip":[axis("gaming_date","temporal","Date"),axis("label","nominal"),axis("coin","quantitative",format="$,.0f")]}}
    ]
    return custom(name,dataset,[field("gaming_date"),*(field(k) for k in fields)],{"layer":layer},title,desc,placement)


def player_page():
    ladder = custom("concentration-curve","ladder",[field(k) for k in
         ("cumulative_player_share","cumulative_theo_share","cumulative_coin_in_share")],{
        "transform":[{"fold":["cumulative_theo_share","cumulative_coin_in_share"],"as":["measure","share"]},
                     {"calculate":"datum.measure === 'cumulative_theo_share' ? 'Tracked theo' : 'Tracked coin-in'","as":"label"}],
        "mark":{"type":"line","strokeWidth":2},
        "encoding":{"x":axis("cumulative_player_share","quantitative","Top share of players",axis={"format":".0%"}),
                    "y":axis("share","quantitative","Cumulative share",axis={"format":".0%"}),
                    "color":axis("label","nominal",scale={"domain":["Tracked theo","Tracked coin-in"],"range":[CYAN,PEWTER]})}
    },"The top tenth generated two-thirds of tracked theo","Jan–Jun player totals, ranked by tracked theo.",pos(0,2,7,6))
    concentration = table("top-shares","concentration",[("top_percent","Top %"),("tracked_theo_share","Theo share",None,PERCENT),
                   ("tracked_coin_in_share","Coin-in share",None,PERCENT),("tracked_player_net_usd","Player net",None,MONEY)],
                   "Top cohorts netted losses","The same ranked players drive both shares.",pos(7,2,5,3),order="`top_percent`")
    outcomes = table("player-outcomes","outcomes",[("outcome","Outcome"),("players","Players"),("player_net_usd","Net",None,MONEY)],
                     "Wagering outcomes include winners","Zero coin-in is no tracked gaming. Exactly-zero bettors are separate.",
                     pos(7,5,5,3))
    hist = custom("net-histogram","hist",[field("band"),field("observations")],{
        "mark":{"type":"bar","color":PEWTER},
        "encoding":{"x":axis("observations","quantitative","Players"),"y":axis("band","nominal","Jan–Jun player net",sort="ascending"),
                    "tooltip":[axis("band","nominal"),axis("observations","quantitative")]}
    },"Most tracked bettors finished down","Win and loss bins use player net. No tracked gaming is labeled separately.",pos(0,8,5,6))
    segments=table("player-segments","segments",[("tier_end","Tier"),("theo_decile","Theo decile"),
                   ("players","Player-months","SUM(player_months)"),("wagers","Coin-in","SUM(coin_in_usd)",MONEY),
                   ("payout","Payout","SUM(payout_usd)",MONEY),("net","Player net","SUM(player_net_usd)",MONEY),
                   ("theo","Theo","SUM(theo_usd)",MONEY),("luck","Luck","SUM(player_luck_usd)",MONEY),
                   ("comp","Comp cost","SUM(comp_cost_usd)",MONEY),("contrib","Contribution","SUM(contribution_usd)",MONEY)],
                   "Tier and play intensity explain different outcomes","Counts are player-months. Use tier, region and age filters.",
                   pos(5,8,7,6),False)
    points=simple_line("comp-price","comps","week_start",[("points_per_face_usd","Points per face dollar")],
                       "Points bought more comp value after May 1","Compare observed redemption prices by gaming week.",pos(0,14,6,5))
    rates=simple_line("comp-rates","comps","week_start",[("reinvestment_tracked","Tracked theo"),("reinvestment_floor","Floor theo")],
                      "Tracked-theo reinvestment rose","Tracked theo is the headline denominator. Floor theo is a secondary view.",
                      pos(6,14,6,5),PERCENT)
    control=table("comp-control","control",[("metric","Measure"),("estimate","Estimate"),("ci90_lower","90% low"),("ci90_upper","90% high")],
                  "The per-player theo decline does not survive the control","Uncarded meters are a floor-level control. No causal player lift is claimed.",
                  pos(0,19,6,5))
    liability=table("points-exposure","points",[("valuation","Basis"),("apr30_usd","Apr 30",None,MONEY),("may28_usd","May 28",None,MONEY),
                  ("excess_valuation_usd","Over normal accrual",None,MONEY)],"Repricing raised outstanding-point exposure",
                  "Full redemption at observed rates, before breakage. See the pilot's reset-adjusted decision value.",pos(6,19,6,5))
    return page("high-roller","High-Roller Ladder",text("players-intro","## THE HIGH-ROLLER LADDER\n\nTracked outcomes describe play. No action targets heavy losers."),
                ladder,concentration,outcomes,hist,segments,points,rates,control,liability)


def action_page():
    allocation = custom("budget-allocation-ai", "cage", [field("spent_usd"), field("kept_usd")], {
        "transform": [
            {"fold": ["spent_usd", "kept_usd"], "as": ["part", "amount"]},
            {"calculate": "datum.spent_usd + datum.kept_usd", "as": "total"},
            {"calculate": "datum.part === 'spent_usd' ? 'Funded' : 'Reserve'", "as": "allocation"},
            {"calculate": "datum.amount / datum.total", "as": "share"},
        ],
        "mark": {"type": "bar", "stroke": IVORY, "strokeWidth": 1},
        "encoding": {
            "x": axis("amount", "quantitative", "July budget", stack="zero", axis={"format": "$~s"}),
            "color": axis("allocation", "nominal", "Allocation", scale={"domain": ["Funded", "Reserve"], "range": [GOLD, JADE]}),
            "tooltip": [axis("allocation", "nominal", "Allocation"),
                        axis("amount", "quantitative", "Amount", format="$,.2f"),
                        axis("share", "quantitative", "Share", format=".1%")],
        },
    }, "The July budget stays mostly in reserve",
        "The counters above label the funded and reserve amounts. Select a segment for its percentage.", pos(0, 5, 12, 4))
    spread = custom("action-board","actions",[field(k) for k in ("action_type_id","target_label","selected","cash_cost_usd",
                    "expected_net_usd","low_net_usd","high_net_usd")],{
        "transform":[{"calculate":"datum.high_net_usd-datum.low_net_usd","as":"spread"},
                     {"calculate":"datum.selected ? 'Funded' : datum.action_type_id === 'A-HOLD' ? 'Hold only' : 'Evaluated'","as":"status"}],
        "mark":{"type":"point","filled":True,"opacity":0.86},
        "encoding":{"x":axis("spread","quantitative","Scenario spread ($)",axis={"format":"$~s"}),
                    "y":axis("expected_net_usd","quantitative","July base net ($)",axis={"format":"$~s"},
                             scale={"type":"symlog","constant":2000}),
                    "size":axis("cash_cost_usd","quantitative","Catalog cost"),
                    "color":axis("status","nominal",scale={"domain":["Funded","Hold only","Evaluated"],"range":[GOLD,IVORY,PEWTER]}),
                    "shape":axis("status","nominal"),
                    "tooltip":[axis("action_type_id","nominal","Action"),axis("target_label","nominal","Target"),
                               axis("expected_net_usd","quantitative","Base net",format="$,.0f"),
                               axis("low_net_usd","quantitative","Low",format="$,.0f"),
                               axis("high_net_usd","quantitative","High",format="$,.0f")]}
    },"Only the inspection clears the funding screens","Spread measures scenario uncertainty. The vertical scale is symmetric log.",
    pos(0,9,12,7))
    cols=[("action_type_id","Action"),("target_label","Target"),("selected","Funded"),("quantity","Qty"),
          ("cash_cost_usd","Cost",None,MONEY),("lead_days","Lead days"),("operating_days","Post-lead days"),
          ("low_net_usd","Low net",None,MONEY),("expected_net_usd","Base net",None,MONEY),("high_net_usd","High net",None,MONEY),
          ("p_mid","Base probability",None,PERCENT),("measurement_date","Readout"),("assumption","Assumption"),("success_rule","Decision rule"),
          ("evidence_view","Evidence source")]
    return page("cashier","Cashier’s Cage",text("cage-intro","## THE CASHIER’S CAGE\n\nAuthorize information worth buying and preserve the rest."),
        counter("spent","cage","MAX(spent_usd)","Funded in July","M-1158 inspection. Pilot deferred on power.",pos(0,2,4,3)),
        counter("kept","cage","MAX(kept_usd)","Kept in reserve","No move, replacement or staffing package funded.",pos(4,2,4,3)),
        counter("hold-ref","cage","0*MAX(spent_usd)","Hold-only net","The alternative preserves the full $100,000.",pos(8,2,4,3)),
        allocation, spread,
        table("cage-slip","actions",cols,"The July slip funds $1,200","Net includes catalog costs and any disruption. Information value is a scenario, not July cash.",
              pos(0,16,12,8),order="CASE WHEN selected THEN 0 ELSE 1 END"),
        table("annual-options","annual",[("action_type_id","Action"),("target_label","Target"),("cash_cost_usd","12-month cost",None,MONEY),
              ("expected_net_usd","Base net",None,MONEY),("low_net_usd","Low",None,MONEY),("high_net_usd","High",None,MONEY)],
              "The bank move and three leases remain on the watchlist","Annual economics do not authorize July funding.",pos(0,24,7,7)),
        table("tech-compare","tech",[("target","Coverage"),("funded_shifts","July shifts"),("package_cost_usd","Cost",None,MONEY),
              ("full_recovery_theo_per_shift","100% theo/shift",None,MONEY)],
              "Neither shift pays for its package","Saturday wins per shift. Grave yields more total July opportunity.",pos(7,24,5,4)),
        table("tech-sensitivity","tech_sensitivity",[("target_label","Target"),("net_lost_theo_minus_30_pct_usd","−30%",None,MONEY),
              ("expected_net_usd","Base",None,MONEY),("net_lost_theo_plus_30_pct_usd","+30%",None,MONEY)],
              "Higher hourly theo still leaves staffing underwater","Downtime-value sensitivity. Other action rows are unchanged.",pos(7,28,5,3)))


def model_page():
    return page("model-room","Model Room",
        text("model-intro","## THE MODEL ROOM\n\nPrioritize Saturday 7–10 p.m. if coverage can clear its cost hurdle."),
        text("cutoff-disclosure", "**Why the primary score changed**\n\nGilded Ace Locals Appreciation Week was announced on May 26, after the April 30 forecast date. We removed it from the forecast, refit through April 30, and scored the frozen May and June forecasts once. Average error fell from $55,270.94 (4.06%) to $51,128.96 (3.84%). The trend model lost because it increased error in April and on the holdout.", 2, 3),
        timeline_chart("model-holdout","forecast","actual_usd",["forecast_usd","baseline_usd"],"The weekday model cuts holdout MAE by 77%",
                       "Frozen Jan–Apr fits. Shaded area is the 61-day May–Jun holdout.",pos(0,5,12,8),"2025-05-01","2025-07-01",
                       ["Weekday + flags","Constant baseline"]),
        table("model-score","scores",[("model","Model"),("scored_days","Scored days"),("mae_usd","MAE",None,MONEY),("mape_pct","MAPE (%)")],
              "MAE fell from $218K to $51K","MAPE is the mean absolute percentage error.",pos(0,13,6,4)),
        table("model-residual","residual",[("local_weekday","Weekday"),("model_mean_residual_usd","Mean residual",None,MONEY),
               ("model_mae_usd","MAE",None,MONEY)],"Check forecast bias by weekday",
               "Residual = actual minus forecast. A negative value means the forecast was too high.",pos(6,13,6,6)),
        text("leakage-check","**Leakage checks**\n\nTrain ends Apr 30. Holdout is frozen. Event announcements must be known by April 30 and precede the gaming date. Weather, tourism and realized play are excluded.",19,2))


def dashboard():
    bindings = [("machine","gaming_date"),("floor","gaming_date"),("traffic","gaming_date"),("demand","gaming_date"),
                ("fault","gaming_date"),("segments","gaming_date"),("comps","gaming_date"),("forecast","gaming_date")]
    filters = [filter_widget("date-range","Gaming dates","filter-date-range-picker",bindings,0,0,4,
                {"range":{"dataType":"DATE","min":{"value":"2025-01-01"},"max":{"value":"2025-06-30"}}})]
    labels = [("zone_name","Zone"),("bank_name","Bank"),("manufacturer","Manufacturer"),
              ("volatility_class","Volatility"),("verdict_chip","Verdict suit"),("machine_id","Machine")]
    for index,(key,label) in enumerate(labels):
        x,y = [(4,0),(8,0),(0,2),(4,2),(8,2),(0,4)][index]
        filters.append(filter_widget(f"filter-{key}",label,"filter-multi-select",[("machine",key), ("traffic",key)] if key=="zone_name" else [("machine",key)],x,y,4))
    for index,(key,label) in enumerate([("tier_end","Tier"),("home_region","Region"),("age_band","Age band")]):
        filters.append(filter_widget(f"filter-{key}",label,"filter-multi-select",[("segments",key)],index*4,6,4))
    pages = [page("pit-boss","Pit Boss",*board()),luck_page(),floor_page(),player_page(),action_page(),model_page(),
             page("evidence-vault","Evidence Vault",text("evidence-intro","## THE EVIDENCE VAULT\n\nTrace each recommendation to the tested alternative and its limitation.\n\n[Ask the Pit Boss in Genie (workspace sign-in required)](https://dbc-a3bbfca6-850a.cloud.databricks.com/genie/rooms/01f1db4548ec16ee9f10853bb4959656?o=7474653288963289)."),
                  table("claims","evidence",[("claim","Claim"),("widget","Page"),("evidence","Gold source and SQL"),
                        ("result","Result"),("alternative_tested","Alternative or rule"),("limitation","Limitation")],
                        "Every recommendation has an evidence trail","Information value and closure effects are scenario or descriptive estimates.",
                        pos(0,2,12,15))),
             page("global-filters","Global filters",*filters,global_filters=True)]
    def both(color):
        return {"light": color, "dark": color}
    theme = {"canvasBackgroundColor":both(CANVAS),"widgetBackgroundColor":both(BAIZE),
             "widgetBorderColor":both(SEAM),"fontColor":both(IVORY),"selectionColor":both(GOLD),
             "visualizationColors":[PEWTER,PURPLE,CYAN,CORAL,BRASS,BONE,JADE,GOLD],"widgetHeaderAlignment":"LEFT"}
    return {"datasets":[{"name": k,"displayName": k.replace("_"," ").title(),"queryLines":[v]} for k,v in datasets().items()],
            "pages":pages,"uiSettings":{"theme":theme}}


def contrast(a, b):
    def luminance(hex_color):
        values = [int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
        linear = [x/12.92 if x <= 0.04045 else ((x+0.055)/1.055)**2.4 for x in values]
        return sum(x*w for x,w in zip(linear,(0.2126,0.7152,0.0722)))
    lo,hi = sorted((luminance(a),luminance(b)))
    return (hi+0.05)/(lo+0.05)


def validate_structure(doc):
    assert doc["pages"][0]["layout"][0]["widget"]["multilineTextboxSpec"]["lines"][0].startswith(f"## {VERDICT}")
    assert len([p for p in doc["pages"] if p["pageType"] == "PAGE_TYPE_CANVAS"]) == 7
    for bg in (CANVAS,BAIZE):
        assert all(contrast(c,bg)>=4.5 for c in (IVORY,SMOKE,GOLD))
        assert all(contrast(c,bg)>=3 for c in (PEWTER,*SUITS.values(),JADE))
    for p in doc["pages"]:
        cells=set()
        for entry in p["layout"]:
            box=entry["position"]
            assert box["x"]+box["width"]<=12
            region={(x,y) for x in range(box["x"],box["x"]+box["width"])
                    for y in range(box["y"],box["y"]+box["height"])}
            assert not cells.intersection(region), p["name"]
            cells.update(region)
            w=entry["widget"]
            assert re.fullmatch(r"[a-zA-Z0-9_-]{1,60}",w["name"])
            if w.get("spec",{}).get("widgetType")=="custom-vega-viz":
                json.loads(w["spec"]["jsonSpec"]["spec"])


def validate_sql(doc, profile, warehouse):
    sys.path.insert(0,str(ROOT/"scripts"))
    from deploy_phase2 import execute_sql
    sources = {d["name"]: "".join(d["queryLines"]) for d in doc["datasets"]}
    checks={f"dataset {k}": f"SELECT * FROM ({v}) AS data LIMIT 1" for k,v in sources.items()}
    for p in doc["pages"]:
        for item in p["layout"]:
            for i,q in enumerate(item["widget"].get("queries",[])):
                q=q["query"]
                cols=", ".join(f"{f['expression']} AS `{f['name']}`" for f in q["fields"])
                group="" if q["disaggregated"] else " GROUP BY ALL"
                checks[f"{item['widget']['name']} {i}"]=f"DESCRIBE QUERY SELECT {cols} FROM ({sources[q['datasetName']]}) data{group}"
    def check(item):
        name,sql=item
        try:
            execute_sql(profile,warehouse,sql)
            return name,None
        except Exception as e:
            return name,str(e)
    with ThreadPoolExecutor(4) as pool:
        results=list(pool.map(check,checks.items()))
    failed=[(n,e) for n,e in results if e]
    if failed:
        raise SystemExit("\n".join(f"{n}\n{e}" for n,e in failed))
    print(f"Validated {len(results)} dataset and widget SQL queries")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-warehouse")
    parser.add_argument("--profile",default="DEFAULT")
    args=parser.parse_args()
    doc=dashboard()
    validate_structure(doc)
    if args.check_warehouse:
        validate_sql(doc,args.profile,args.check_warehouse)
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    print(OUT)


if __name__=="__main__":
    main()
