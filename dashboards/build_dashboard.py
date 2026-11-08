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
         "♠ REPLACE (long-term candidate)": BONE, "🔍 INSPECT": JADE}
VERDICT = "We recommend not replacing any of the ten lowest-earning machines in July. Their low earnings come mostly from the Back Forty's lost foot traffic and from game settings, so we spend $10,500 on three tests: new signage for the Back Forty, a payout check on machine M-1158, and moving machine M-1184 to a busier spot to learn whether its weakness is the spot or the machine. We keep $89,500 in reserve."
MONEY = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
HOLD_PERCENT = {"type": "number-percent", "decimalPlaces": {"type": "exact", "places": 2}}
PERCENT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 2}}

GAMING_HOURS = [f"{(hour % 12) or 12}{'a' if hour < 12 else 'p'}"
                for hour in (*range(6, 24), *range(6))]
HOUR_TRANSFORM = {"calculate": f"{json.dumps(GAMING_HOURS)}[datum.gaming_hour]", "as": "hour_label"}


COMP_LABELS = {
    "relative_coin_in_pct": "Change in tracked wagers relative to untracked wagers",
    "relative_coin_in_usd_week": "Change in tracked wagers per week relative to untracked wagers",
    "carded_share_pp": "Change in the tracked share of wagers",
    "tracked_theo_per_player_raw_usd": "Change in expected win per tracked player before comparison",
    "tracked_theo_per_player_control_adjusted_usd": "Change in expected win per tracked player after comparison",
}


def money_sql(value, cents=False):
    small = 2 if cents else 0
    return (f"CONCAT(IF(({value})<0, '−', ''), '$', CASE "
            f"WHEN ABS({value})>=999950 THEN CONCAT(FORMAT_NUMBER(ABS({value})/1000000,1),'M') "
            f"WHEN ABS({value})>=10000 THEN CONCAT(FORMAT_NUMBER(ABS({value})/1000,1),'K') "
            f"ELSE FORMAT_NUMBER(ABS({value}),{small}) END)")


def comp_result_sql(value, key="metric"):
    return (f"CASE WHEN {key}='relative_coin_in_usd_week' THEN {money_sql(value)} "
            f"WHEN {key} LIKE 'tracked_theo_per_player%usd' THEN {money_sql(value, cents=True)} "
            f"WHEN {key}='relative_coin_in_pct' THEN CONCAT(FORMAT_NUMBER({value},2),'%') "
            f"ELSE CONCAT(FORMAT_NUMBER({value},2),' percentage points') END")


def evidence_result_sql():
    amount = "CAST(amount AS DOUBLE)"
    prefix = r"r'USD (-?\d+(?:\.\d+)?)'"
    suffix = r"r'(-?\d+(?:\.\d+)?) USD'"
    return (f"AGGREGATE(REGEXP_EXTRACT_ALL(result, {suffix}, 1), "
            f"AGGREGATE(REGEXP_EXTRACT_ALL(result, {prefix}, 1), result, "
            f"(output, amount) -> REPLACE(output, CONCAT('USD ', amount), {money_sql(amount)})), "
            f"(output, amount) -> REPLACE(output, CONCAT(amount, ' USD'), {money_sql(amount)}))")


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
    date = {"fieldName": date_field, "displayName": "Week starting", "scale": {"type": "temporal"}}
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


def model_review_queries():
    review = json.loads((ROOT / "twin/forecast-review.json").read_text())
    names = [
        ("Constant baseline", "Constant baseline", "Constant baseline"),
        ("Seasonal (weekday mean) baseline", "Seasonal (weekday mean) baseline", "Seasonal (weekday mean) baseline"),
        ("Current ridge", "current", "Weekday + events model (primary)"),
        ("Ridge with a trend", "trend", "Trend model (tested, rejected)"),
    ]
    scores = []
    bias = []
    for index, (key, april, label) in enumerate(names):
        row = review["holdout"][key]
        scores.append(f"({index}, '{label}', {review['april'][april]['mae']}, {row['mae']}, {row['mape']/100})")
    for index, (day, row) in enumerate(review["bias"].items()):
        measures = ", ".join(str(row[key]) for key, _, _ in names)
        bias.append(f"({index}, '{day}', {measures})")
    return {
        "model_comparison": f"SELECT * FROM VALUES {', '.join(scores)} AS t(rank,model,april_usd,holdout_usd,mape)",
        "model_bias": f"SELECT * FROM VALUES {', '.join(bias)} AS t(rank,weekday,constant_usd,seasonal_usd,primary_usd,trend_usd)",
    }


def schedule_query():
    return f"""
      WITH tasks AS (
        SELECT CASE action_type_id WHEN 'A-INSPECT' THEN 'Inspect M-1158' ELSE 'Move M-1184' END action,
               CASE action_type_id WHEN 'A-INSPECT' THEN 'Wed' ELSE 'Thu' END eligible_weekday,
               CAST(downtime_minutes / 60 AS INT) AS hours
        FROM {SCHEMA}gold_action_plan WHERE selected AND horizon_days=30
        AND action_type_id IN ('A-INSPECT','A-MOVE-MACHINE')
      ), windows AS (
        SELECT t.action,t.hours,h.local_weekday,h.gaming_hour,
               SUM(p.theo_per_available_machine_hour) AS lost_theo_usd
        FROM tasks t CROSS JOIN {SCHEMA}gold_forecast_tech_timing h
        JOIN {SCHEMA}gold_forecast_tech_timing p ON p.local_weekday=h.local_weekday
          AND p.gaming_hour>=h.gaming_hour AND p.gaming_hour<h.gaming_hour+t.hours
        WHERE (h.local_weekday=t.eligible_weekday AND h.gaming_hour+t.hours<=24)
           OR (h.local_weekday='Sat' AND h.gaming_hour=13)
        GROUP BY ALL HAVING COUNT(*)=t.hours
      ), ranked AS (
        SELECT *,ROW_NUMBER() OVER (PARTITION BY action,local_weekday ORDER BY lost_theo_usd,gaming_hour) AS preference
        FROM windows
      )
      SELECT action,MAX(hours)*60 AS minutes,
             MAX(IF(local_weekday<>'Sat',local_weekday,NULL)) AS weekday,
             MAX(IF(local_weekday<>'Sat',gaming_hour,NULL)) AS start_hour,
             MAX(IF(local_weekday<>'Sat',lost_theo_usd,NULL)) AS quiet_usd,
             MAX(IF(local_weekday='Sat',lost_theo_usd,NULL)) AS saturday_usd
      FROM ranked WHERE preference=1 GROUP BY action
    """


def datasets():
    return {
        "machine": f"""SELECT d.*, v.verdict_chip, v.gm_rank, v.adjusted_rank, v.last_zone, v.last_bank_name
            FROM {SCHEMA}gold_machine_day d JOIN {SCHEMA}gold_machine_verdict v USING (machine_id)""",
        "tribunal": f"SELECT d.*, v.verdict_chip, v.gm_rank, v.last_bank_name FROM {SCHEMA}gold_machine_day d JOIN {SCHEMA}gold_machine_verdict v USING (machine_id) WHERE v.gm_rank<=10",
        "action_schedule": schedule_query(),
        **model_review_queries(),
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
        "walkway": f"""SELECT *, CASE phase WHEN 'pre' THEN 'Before' WHEN 'closure' THEN 'During closure'
            ELSE 'After' END AS period FROM {SCHEMA}gold_walkway_did""",
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
        "hold_case": f"{source('gold_action_plan')} WHERE horizon_days=30 AND action_type_id='A-HOLD'",
        "tech": f"""{source('gold_tech_shift_economics')} WHERE horizon_days=30""",
        "forecast": source("gold_forecast_day"),
        "scores": f"""SELECT model, scored_days, mae_usd, mape_pct FROM {SCHEMA}gold_forecast_holdout_metrics
             UNION ALL SELECT 'weekday_ridge_linear_trend', 61, 66519.66, 5.00""",
        "residual": source("gold_forecast_weekday_residual"),
        "evidence": source("gold_claims_evidence"),
    }


def board():
    return [
        text("verdict", f"## {VERDICT}\n\n**THE GILDED ACE · EYE IN THE SKY** · Fictional casino · Jan–Jun 2025 evidence\n\n**Comp monitoring:** review comp pricing and tracked play if cost exceeds 1.50% of tracked theo for two consecutive complete gaming weeks.\n\n[Ask the Pit Boss in Genie (workspace sign-in required)](https://dbc-a3bbfca6-850a.cloud.databricks.com/genie/rooms/01f1db4548ec16ee9f10853bb4959656?o=7474653288963289).", h=5),
        counter("health", "machine", "SUM(theo_usd)/NULLIF(SUM(theo_usd + leak_usd + location_opportunity_usd),0)",
                "Theo captured", "Share of the floor’s earning potential we actually captured. Theo is the amount the house expects to win.", pos(0, 5, 2, 3), PERCENT),
        counter("coin", "machine", "SUM(coin_in_usd)", "Coin-in", "Total wagers in the current slice.", pos(2, 5, 2, 3)),
        counter("hold", "machine", "SUM(house_win_usd)/NULLIF(SUM(coin_in_usd),0)", "Actual hold",
                "House win divided by wagers.", pos(4, 5, 2, 3), HOLD_PERCENT),
        counter("theo-hold", "machine", "SUM(theo_usd)/NULLIF(SUM(coin_in_usd),0)", "Theo hold",
                "Expected win divided by wagers.", pos(6, 5, 2, 3), HOLD_PERCENT),
        counter("luck", "machine", "SUM(luck_residual_usd)", "Luck", "Actual win minus expected win.", pos(8, 5, 2, 3)),
        counter("leak", "machine", "SUM(leak_usd)", "Lost to downtime", "Estimated expected win missed while machines were unavailable.", pos(10, 5, 2, 3)),
        counter("comp-kpi", "floor", "SUM(comp_cost_usd)/NULLIF(SUM(tracked_theo_usd),0)",
                "Comp reinvestment", "Tracked theo denominator. Floor-wide, date filter only.", pos(0, 8, 4, 3), PERCENT),
        counter("sigma-kpi", "machine", "SUM(luck_residual_usd)/NULLIF(SQRT(SUM(luck_variance_usd2)),0)",
                "Luck z-score", "A magnitude under 2 is within the two-sigma screen.", pos(4, 8, 4, 3), None),
        counter("cash-kept", "cage", "MAX(kept_usd)", "Kept in the cage", "July plan is a fixed decision snapshot.", pos(8, 8, 4, 3)),
        table("tribunal", "tribunal", [("machine_id","Machine"),("gm_rank","GM rank"),("last_bank_name","Last bank"),
                    ("verdict_chip","Verdict"),("win","Win in slice","SUM(house_win_usd)",MONEY)],
              "The general manager’s ten lowest earners", "Rank uses the six-month study. The win column uses the selected gaming dates.",
              pos(0, 11, 12, 6), False, "`gm_rank`"),
        bridge(),
        table("adjusted", "adjusted", [("adjusted_rank","Rank"),("machine_id","Machine"),("last_bank_name","Bank"),
              ("verdict_chip","Verdict"),("floor_days","Floor days"),("net_benefit_12m_usd","12-month net",None,MONEY),
              ("payback_label","Payback","COALESCE(CAST(payback_month AS STRING), 'Does not pay back within 12 months')")], "The adjusted list identifies three long-term candidates",
              "Full-window ranks and lease economics. None clears the July screen.", pos(0, 22, 12, 6), order="`adjusted_rank`"),
        table("cage-overview","cage",[("spent_usd","Funded",None,MONEY),("kept_usd","Kept",None,MONEY),
              ("funded_action_types","Funded types")],"Three tests and no July replacements",
              "See the Evidence Vault for assumptions and alternative explanations.",pos(0, 28,12,3))
    ]


def bridge():
    labels = ["Downtime", "Location", "Game mix", "Machine effect", "Luck"]
    names = ["leak", "location", "lineup", "machine_effect", "luck"]
    exprs = ["-leak_usd", "location_usd", "lineup_usd", "machine_specific_usd", "luck_residual_usd"]
    return custom("bridge", "machine", [field(k, f"SUM({v})") for k,v in zip(names,exprs)], {
        "transform": [{"fold": names, "as": ["step", "amount"]},
                      {"calculate": f"{json.dumps(labels)}[indexof({json.dumps(names)}, datum.step)]", "as": "component"}],
        "mark": "bar",
        "encoding": {"y": axis("component", "ordinal", "Component", sort=labels),
                     "x": axis("amount", "quantitative", "Effect on win", axis={"format": "$.3~s"}),
                     "color": axis("component", "nominal", scale={"domain": labels, "range": [CORAL,CYAN,BRASS,BONE,PURPLE]}, legend=None),
                     "tooltip": [axis("component", "nominal", "Component"), axis("amount", "quantitative", "Effect on win", format="$,.0f")]}
    }, "Five effects on win", "These effects explain the difference between potential and actual win. The bars use their own scale.", pos(0,17,12,5), False)


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
            {"data":{"values":[{"x":13,"y":115,"zone":"Back Forty"},{"x":105,"y":88,"zone":"Bar Row"},
                 {"x":5,"y":61,"zone":"Main Entrance"},{"x":111,"y":115,"zone":"Garage Entrance"},
                 {"x":105,"y":15,"zone":"High-Limit Room"},{"x":62,"y":1,"zone":"Hotel Corridor"},
                 {"x":58,"y":70,"zone":"Center Pit"}]},
             "mark":{"type":"text","color":IVORY,"fontWeight":600,"dy":-8},
             "encoding":{"x":axis("x","quantitative",scale={"zero":False}),
                         "y":axis("y","quantitative",scale={"zero":False}),"text":{"field":"zone"}}},
            {"data":{"values":[{"x":27.5,"y":106,"spot":"M-1184 old slot L-33-6"},{"x":69,"y":50,"spot":"M-1184 new slot L-07-3"}]},
             "mark":{"type":"point","shape":"cross","size":140,"strokeWidth":2,"color":IVORY},
             "encoding":{"x":axis("x","quantitative",scale={"zero":False}),"y":axis("y","quantitative",scale={"zero":False}),
                         "tooltip":[axis("spot","nominal","Test move")]}}
        ]
    },"Bank positions reveal local clusters","Dots show slot positions. The walkway reopened April 7 after closing March 3. Crosses mark the old and new slots for M-1184.",pos(0,2,7,8),False)
    def heat(name, expr, title, description, placement, color):
        return custom(name,"traffic",[field("zone_name"),field("gaming_hour"),field("metric",expr)],{
            "transform":[HOUR_TRANSFORM, {"filter":"isValid(datum.metric) && isFinite(datum.metric)"}], "mark":"rect","encoding":{"x":axis("hour_label","ordinal","Gaming hour",sort=GAMING_HOURS),
                "y":axis("zone_name","nominal","Zone"),
                "color":axis("metric","quantitative",title,scale={"range":[BAIZE,color]}),
                "tooltip":[axis("zone_name","nominal","Zone"),axis("hour_label","nominal","Gaming hour"),axis("metric","quantitative",title,format=",.1f")]}
        },title,description,placement,False)
    traffic=heat("traffic-heat","CAST(60.0*SUM(entries)/NULLIF(SUM(coverage_minutes),0) AS DOUBLE)","Counters peak at different hours",
                 "Crossings per covered sensor-hour. Blanks indicate no coverage.",pos(7,2,5,4),CYAN)
    leak=heat("leak-heat","SUM(lost_theo_usd)","Downtime costs most at busy hours",
              "Estimated lost theo weights unavailable time by hour.",pos(7,6,5,4),CORAL)
    timeline = timeline_chart("demand-timeline","demand","coin_in_usd",["forecast_usd"],"Back Forty weakened during the closure",
                              "Actual wagers and the frozen forecast. The shaded area marks the May and June test period.",pos(0,10,12,7),
                              "2025-05-01","2025-07-01",["Forecast"])
    compare = custom("walkway-did","walkway",[field(k) for k in ("period","back_forty_index","control_index")],{
        "transform":[{"fold":["back_forty_index","control_index"],"as":["series","value"]},
                     {"calculate":"datum.series === 'back_forty_index' ? 'Back Forty' : 'Rest of floor'","as":"group"}],
        "mark":{"type":"line","point":True},"encoding":{"x":axis("period","ordinal","Walkway phase",sort=["Before","During closure","After"],axis={"labelAngle":0}),
            "y":axis("value","quantitative","Pre = 100",scale={"zero":False}),
            "color":axis("group","nominal","Area",scale={"domain":["Back Forty","Rest of floor"],"range":[CYAN,PEWTER]})}
    },"Back Forty fell to 71 while controls reached 103","Coin-in per installed machine-day. The pre-trend limits causal attribution.",pos(0,17,6,5))
    faults = custom("fault-hour","fault",[field("gaming_hour"),field("wait","AVG(wait_seconds)/3600.0"),
                                       field("work","AVG(work_seconds)/3600.0")],{
        "transform":[HOUR_TRANSFORM,{"fold":["wait","work"],"as":["part","hours"]},
                      {"calculate":"datum.part === 'wait' ? 'Waiting for a technician' : 'Repair time'","as":"delay"}],
        "mark":"bar","encoding":{"x":axis("hour_label","ordinal","Gaming hour",sort=GAMING_HOURS),
           "y":axis("hours","quantitative","Mean hours"),"color":axis("delay","nominal","Time spent",scale={"range":[CORAL,PEWTER]})}
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
                     "color":axis("label","nominal","Series",scale={"domain":legend,"range":[IVORY,CYAN,PEWTER][:len(legend)]}),
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
                    "color":axis("label","nominal","Series",scale={"domain":["Tracked theo","Tracked coin-in"],"range":[CYAN,PEWTER]})}
    },"The top tenth generated two-thirds of tracked theo","The theo and coin-in lines overlap almost exactly.",pos(0,2,7,6))
    concentration = table("top-shares","concentration",[("top_group","Player group","CONCAT('Top ', CAST(CAST(top_percent AS INT) AS STRING), '%')"),("tracked_theo_share","Theo share",None,PERCENT),
                   ("tracked_coin_in_share","Coin-in share",None,PERCENT),("tracked_player_net_usd","Player net",None,MONEY)],
                   "Top cohorts netted losses","The same ranked players drive both shares.",pos(7,2,5,3),order="`top_percent`")
    outcomes = table("player-outcomes","outcomes",[("outcome_label","Outcome","CASE LOWER(outcome) WHEN 'loser' THEN 'Finished down' WHEN 'winner' THEN 'Finished up' WHEN 'exactly zero' THEN 'Exactly even' ELSE outcome END"),("players","Players"),("player_net_usd","Net",None,MONEY)],
                     "Wagering outcomes include winners","Zero coin-in is no tracked gaming. Exactly-zero bettors are separate.",
                     pos(7,5,5,3))
    hist = custom("net-histogram","hist",[field("band","REGEXP_REPLACE(band, '^[0-7] ', '')"),field("bin_id"),field("observations")],{
        "mark":{"type":"bar","color":PEWTER},
        "encoding":{"x":axis("observations","quantitative","Players",axis={"format":",d"}),"y":axis("band","nominal","Jan–Jun player net",sort={"field":"bin_id","order":"ascending"}),
                    "tooltip":[axis("band","nominal","Player result"),axis("observations","quantitative","Players",format=",d")]}
    },"Most tracked bettors finished down","Win and loss bins use player net. No tracked gaming is labeled separately.",pos(0,8,5,6))
    segments=table("player-segments","segments",[("tier_end","Tier"),("theo_decile","Theo decile"),
                   ("players","Player-months","SUM(player_months)"),("wagers","Coin-in","SUM(coin_in_usd)",MONEY),
                   ("payout","Payout","SUM(payout_usd)",MONEY),("net","Player net","SUM(player_net_usd)",MONEY),
                   ("theo","Theo","SUM(theo_usd)",MONEY),("luck","Luck","SUM(player_luck_usd)",MONEY),
                   ("comp","Comp cost","SUM(comp_cost_usd)",MONEY),("contrib","Contribution","SUM(contribution_usd)",MONEY)],
                   "Tier and play intensity explain different outcomes","Counts are player-months. Decile 1 is the highest group by tracked expected win. Use tier, region and age filters.",
                   pos(5,8,7,6),False,order="`tier_end`, `theo_decile`")
    points=simple_line("comp-price","comps","week_start",[("points_per_face_usd","Points per face dollar")],
                       "Points bought more comp value after May 1","Compare observed redemption prices by gaming week.",pos(0,14,6,5))
    rates=simple_line("comp-rates","comps","week_start",[("reinvestment_tracked","Tracked theo"),("reinvestment_floor","Floor theo")],
                      "Tracked-theo reinvestment rose","Tracked theo is the headline denominator. Floor theo is a secondary view.",
                      pos(6,14,6,5),PERCENT)
    comp_label = "CASE metric " + " ".join(f"WHEN '{key}' THEN '{value}'" for key,value in COMP_LABELS.items()) + " ELSE metric END"
    control=table("comp-control","control",[("metric","Measure",comp_label),("estimate","Estimate",comp_result_sql("estimate")),
                  ("ci90_lower","90% low",comp_result_sql("ci90_lower")),("ci90_upper","90% high",comp_result_sql("ci90_upper"))],
                  "The per-player theo decline does not survive the control","Uncarded meters are a floor-level control. No causal player lift is claimed.",
                  pos(0,19,6,5))
    liability=table("points-exposure","points",[("valuation","Basis","CASE valuation WHEN 'face' THEN 'Face value' ELSE 'Economic cost' END"),("apr30_usd","Apr 30",None,MONEY),("may28_usd","May 28",None,MONEY),
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
        "$10,500 funded (10.5%) for Back Forty signage, the M-1158 inspection and the M-1184 move. $89,500 reserve (89.5%).", pos(0, 5, 12, 4))
    spread = custom("action-board","actions",[field(k) for k in ("action_name","action_type_id","target_label","selected","expected_net_usd","low_net_usd","high_net_usd")],{
        "transform":[{"calculate":"datum.action_name + ' (' + datum.action_type_id + ') · ' + datum.target_label","as":"action"},
                     {"calculate":"datum.selected ? 'Funded' : 'Unfunded'","as":"status"}],
        "encoding":{"y":axis("action","nominal","July option",sort={"field":"expected_net_usd","order":"descending"},axis={"labelLimit":420})},
        "layer":[
            {"mark":"bar","encoding":{
                "x":axis("expected_net_usd","quantitative","July net value",axis={"format":"$.3~s"}),
                "color":axis("status","nominal","Funding",scale={"domain":["Funded","Unfunded"],"range":[GOLD,PEWTER]}),
                "tooltip":[axis("action","nominal","Action"),axis("expected_net_usd","quantitative","July net value",format="$,.0f"),
                           axis("low_net_usd","quantitative","Low estimate",format="$,.0f"),axis("high_net_usd","quantitative","High estimate",format="$,.0f")]}},
            {"mark":{"type":"rule","color":IVORY,"strokeWidth":2},"encoding":{
                "x":axis("low_net_usd","quantitative","July net value"),"x2":{"field":"high_net_usd"}}}]
    },"July net value by action","The lines show the low to high estimates. The M-1184 move is funded to test its location.",pos(0,9,12,12))
    cols=[("action_label","Action","CONCAT(action_name, ' (', action_type_id, ')')"),
          ("target_label","Target"),("funded_label","Funded","CASE WHEN selected THEN 'Yes' ELSE 'No' END"),
          ("cash_cost_usd","Cost",None,MONEY),("expected_net_usd","Base net",None,MONEY),
          ("range_label","Range",f"CONCAT({money_sql('low_net_usd')}, ' to ', {money_sql('high_net_usd')})")]
    return page("cashier","Cashier’s Cage",text("cage-intro","## THE CASHIER’S CAGE\n\nThe 60-day pilot can detect a smaller change in percentage terms (5.77% versus 6.44%), even though the dollar change is larger ($7.61 versus $4.15). Expected win accumulates over more days. Wait until the pilot can detect a change of 2.50% or less."),
        counter("spent","cage","MAX(spent_usd)","Funded in July","Add Back Forty signage, inspect M-1158 and move M-1184. Wait on the comp pilot until it can give a clear answer.",pos(0,2,4,3)),
        counter("kept","cage","MAX(kept_usd)","Kept in reserve","Reserve funds for decisions after the July tests.",pos(4,2,4,3)),
        counter("hold-ref","hold_case","COALESCE(MAX(expected_net_usd),0)","Hold-only net","The alternative preserves the full $100,000.",pos(8,2,4,3)),
        allocation, spread,
        table("cage-slip","actions",cols,"The July slip funds three tests","Net includes catalog costs and any disruption. Information value is a scenario, not July cash.",
              pos(0,21,12,8),order="CASE WHEN selected THEN 0 ELSE 1 END"),
        table("annual-options","annual",[("action_label","Action","CONCAT(action_name, ' (', action_type_id, ')')"),("target_label","Target"),("cash_cost_usd","12-month cost",None,MONEY),
              ("expected_net_usd","Base net",None,MONEY),("low_net_usd","Low",None,MONEY),("high_net_usd","High",None,MONEY)],
              "Compare the 12-month action scenarios","Annual estimates assume the gap and effects persist. With no signage effect, the loss is $7,500. See the low case in the table.",pos(0,29,7,7)),
        table("tech-compare","tech",[("target","Coverage"),("funded_shifts","July shifts"),("package_cost_usd","Cost",None,MONEY),
              ("full_recovery_theo_per_shift","100% theo/shift",None,MONEY)],
              "Neither shift pays for its package","Saturday wins per shift. Grave yields more total July opportunity.",pos(7,29,5,4)),
        table("tech-sensitivity","tech_sensitivity",[("target_label","Target"),("net_lost_theo_minus_30_pct_usd","−30%",None,MONEY),
              ("expected_net_usd","Base",None,MONEY),("net_lost_theo_plus_30_pct_usd","+30%",None,MONEY)],
              "Higher hourly theo still leaves staffing underwater","Downtime-value sensitivity. Other action rows are unchanged.",pos(7,33,5,3)),
        text("test-measurement","At the end of August, extend signs if both Back Forty gaps close by at least 25% against the rest of the floor. Otherwise revisit the bank-move test. Judge M-1184 against same-setting Center Pit peers because signage affects Back Forty.",36,3))


def model_page():
    return page("model-room","Model Room",
        text("model-intro","## THE MODEL ROOM\n\nThe forecast shows Saturday 7 to 10 p.m. is the busiest window, but even full technician coverage there would not pay for itself in July."),
        text("cutoff-disclosure", "**Why the primary score changed**\n\nGilded Ace Locals Appreciation Week was announced on May 26, after the April 30 forecast date. We removed it from the forecast, refit through April 30, and scored the frozen May and June forecasts once. Average error fell from $55,271 (4.06%) to $51,129 (3.84%). The trend model lost because it increased error in April and on the holdout.", 2, 3),
        timeline_chart("model-holdout","forecast","actual_usd",["forecast_usd","baseline_usd"],"The weekday model cuts holdout MAE by 77%",
                       "Frozen Jan–Apr fits. Shaded area is the 61-day May–Jun holdout.",pos(0,5,12,8),"2025-05-01","2025-07-01",
                       ["Weekday + flags","Constant baseline"]),
        text("model-choice", 'The weekday-mean baseline had the lowest April validation error at $40,715. The weekday, events and holidays model had the lowest May–June error at $51,129, compared with $68,699 for the weekday mean. We chose the primary model before adding the weekday baseline and kept that choice without using the holdout to switch models. A simple weekday average does almost as well, so events and holidays add modest accuracy.', 13, 3),
        table("model-score","model_comparison",[("model","Model"),("april_usd","April validation error",None,MONEY),
              ("holdout_usd","May–June error",None,MONEY),("mape","MAPE",None,PERCENT)],
              "Four frozen forecasts compared","April fits use January through March. May and June fits use January through April. MAPE means average absolute percentage error.",pos(0,16,12,5),order="`rank`"),
        table("model-residual","model_bias",[("weekday","Weekday"),("constant_usd","Constant",None,MONEY),
               ("seasonal_usd","Seasonal",None,MONEY),("primary_usd","Primary",None,MONEY),("trend_usd","Trend",None,MONEY)],
               "Forecast bias by weekday","Residual is actual minus forecast. A negative value means the forecast was too high.",pos(0,21,12,6),order="`rank`"),
        table("action-schedule","action_schedule",[("action","Action"),("minutes","Minutes offline"),
               ("window","Lowest-value window",f"CONCAT(weekday, ' gaming day, ', ELEMENT_AT(ARRAY({','.join(repr(h) for h in GAMING_HOURS)}), CAST(start_hour AS INT)+1))"),
               ("quiet_usd","Expected win lost",None,MONEY),("saturday_usd","Saturday at 7 p.m.",None,MONEY)],
               "Schedule machine tests in the quietest window","The April-frozen hourly profile compares the first eligible gaming day's quietest window with the same duration at 7 p.m. Saturday.",pos(0,27,12,5)))


def evidence_table():
    route = """CASE WHEN evidence LIKE 'gold_points_liability_bridge%' OR evidence LIKE 'gold_comp_control%' THEN 'comps'
        WHEN widget IN ('Tribunal','Pit Boss','Luck Funnel') THEN 'luck'
        WHEN widget='Floor Radar' THEN 'demand' WHEN widget='High-Roller Ladder' THEN 'players'
        WHEN widget LIKE 'Cashier%' THEN 'plan' WHEN widget='Model Room' THEN 'model' ELSE 'evidence' END"""
    names = {"luck":"Q1 · Machines","demand":"Q2 · Demand","players":"Q4 · Players",
             "comps":"Q5 · Comps","plan":"Q6 · July plan","model":"Model Room","evidence":"Evidence Vault"}
    label = "CASE ("+route+") "+" ".join(f"WHEN '{key}' THEN '{value}'" for key,value in names.items())+" END"
    action_names = {
        "A-INSPECT":"Inspect machine","A-MOVE-MACHINE":"Move machine","A-WAYFINDING":"Install new signs",
        "A-MOVE-BANK":"Move bank","A-REPLACE-LEASE":"Lease replacement","A-REPLACE-BUY":"Buy replacement",
        "A-TECH-SHIFT":"Add technician coverage","A-PREVENTIVE":"Preventive maintenance","A-COMP-PILOT":"Test comp policy",
        "A-COMP-CHANGE":"Change comp redemption rate","A-PROMO":"Run promotion","A-SURVEY":"Survey guests",
    }
    action_label = "CASE SPLIT_PART(claim, ' · ', 1) " + " ".join(
        f"WHEN '{code}' THEN CONCAT('{name} ({code})', SUBSTRING(claim, {len(code)+1}))"
        for code,name in action_names.items()
    ) + " ELSE claim END"
    out = table("claims","evidence",[("claim","Claim",action_label),("page_label","Page",label),("evidence","Gold source and SQL"),
                ("result","Result",evidence_result_sql()),("alternative_tested","Alternative tested"),("limitation","Limitation")],
                "Every recommendation has an evidence trail","Follow the link to its public dashboard view.",pos(0,0,12,16))
    widget = out["widget"]
    widget["queries"][0]["query"]["fields"].append(field("page_url",f"CONCAT('https://gilded-ace-royale.vercel.app/#/', {route})"))
    widget["spec"]["encodings"]["columns"][1]["link"] = {"templatedURL": "{{page_url}}"}
    return out


def dashboard():
    bindings = [("machine","gaming_date"),("tribunal","gaming_date"),("floor","gaming_date"),("traffic","gaming_date"),("demand","gaming_date"),
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
             page("evidence-vault","Evidence Vault",evidence_table(),
                  text("genie-link","[Ask the Pit Boss in Genie (workspace sign-in required)](https://dbc-a3bbfca6-850a.cloud.databricks.com/genie/rooms/01f1db4548ec16ee9f10853bb4959656?o=7474653288963289).",16,2)),
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
