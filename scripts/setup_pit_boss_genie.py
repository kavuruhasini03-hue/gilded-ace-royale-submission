"""Create the workspace-only Pit Boss Genie space with curated Gold SQL."""
import json
from uuid import NAMESPACE_URL, uuid5

from deploy_phase2 import cli, execute_sql

TITLE = "Ask the Pit Boss"
WAREHOUSE = "46ae4ab074f3051d"
PROFILE = "DEFAULT"
SCHEMA = "workspace.royale."
QUESTIONS = [
 ("What were the verdicts for the general manager's bottom ten machines?",
  f"""SELECT gm_rank,machine_id,last_bank_name,verdict_chip,ROUND(house_win_usd,2) AS house_win_usd
      FROM {SCHEMA}gold_machine_verdict WHERE gm_rank<=10 ORDER BY gm_rank"""),
 ("How did Back Forty foot traffic change during the walkway closure?",
  f"""WITH phases AS (
       SELECT CASE WHEN gaming_date < DATE '2025-03-03' THEN '1 Before'
                   WHEN gaming_date < DATE '2025-04-07' THEN '2 Closed' ELSE '3 After' END AS phase,
              IF(zone_id='Z-B40','Back Forty','Rest of floor') AS area, entries, coverage_minutes
       FROM {SCHEMA}gold_zone_gaming_hour
       WHERE gaming_date BETWEEN DATE '2025-01-01' AND DATE '2025-06-30'
         AND entries IS NOT NULL AND coverage_minutes>0)
      SELECT phase,area,ROUND(60.0*SUM(entries)/SUM(coverage_minutes),2) AS entries_per_covered_hour
      FROM phases GROUP BY phase,area ORDER BY phase,area"""),
 ("How much downtime and lost expected win did Ridgeline have?",
  f"""SELECT manufacturer,ROUND(SUM(downtime_hours),2) AS downtime_hours,
      ROUND(SUM(leak_usd),2) AS lost_expected_win_usd FROM {SCHEMA}gold_machine_day
      WHERE active AND location_id IS NOT NULL AND manufacturer='Ridgeline'
        AND gaming_date BETWEEN DATE '2025-01-01' AND DATE '2025-06-30' GROUP BY manufacturer"""),
 ("Why are we inspecting M-1158 and how much does it cost?",
  f"""SELECT v.machine_id,ROUND(v.luck_z,2) AS house_win_surprise_score,v.verdict_chip,
      ROUND(v.house_win_usd,2) AS actual_house_win_usd,ROUND(v.theo_usd,2) AS expected_house_win_usd,
      ROUND(v.theo_usd-v.house_win_usd,2) AS payout_above_expected_usd,
      a.cash_cost_usd,ROUND(a.expected_net_usd,2) AS expected_net_value_usd,a.selected,a.success_rule
      FROM {SCHEMA}gold_machine_verdict v JOIN {SCHEMA}gold_action_plan a ON v.machine_id=a.target_id
      WHERE v.machine_id='M-1158' AND a.action_type_id='A-INSPECT' AND a.horizon_days=30"""),
 ("How did the May 1 comp repricing change points per dollar of face value?",
  f"""SELECT week_start,ROUND(SUM(points_redeemed)/NULLIF(SUM(comp_face_usd),0),2)
        AS observed_points_spent_per_face_dollar FROM {SCHEMA}gold_comp_week
      WHERE gaming_days=7 AND week_start IN (DATE '2025-04-21',DATE '2025-05-05')
      GROUP BY week_start ORDER BY week_start"""),
 ("What is funded in the July budget and how much stays in reserve?",
  f"""SELECT 100000 AS july_budget_usd,SUM(cash_cost_usd) AS spent_usd,
      100000-SUM(cash_cost_usd) AS reserve_usd,
      CONCAT_WS(', ',SORT_ARRAY(COLLECT_SET(IF(action_type_id<>'A-HOLD',target_label,NULL)))) AS funded_targets
      FROM {SCHEMA}gold_action_plan WHERE selected AND horizon_days=30"""),
]
TABLES = ("gold_machine_verdict", "gold_machine_day", "gold_zone_gaming_hour", "gold_floor_day",
          "gold_downtime_ticket", "gold_player_segment_month", "gold_comp_week", "gold_action_plan")


def key(prefix, question):
    return uuid5(NAMESPACE_URL, "gilded-ace-genie/"+prefix+"/"+question).hex


def main():
    for question, query in QUESTIONS:
        if not execute_sql(PROFILE, WAREHOUSE, query):
            raise RuntimeError("Empty answer for: "+question)
    spaces = json.loads(cli(PROFILE, "genie", "list-spaces"))
    if isinstance(spaces, dict):
        spaces = spaces.get("spaces", [])
    existing = next((s for s in spaces if s["title"] == TITLE), None)
    spec = {"version": 2, "config": {"sample_questions": [
        {"id":key("sample", question), "question":[question]} for question,_ in QUESTIONS]},
        "data_sources": {"tables":[{"identifier":SCHEMA+t} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions":[{"id":key("instruction", TITLE),"content":[
                "The Gilded Ace is fictional. Answer in plain English using only the eight listed Gold sources.",
                "A gaming day runs from 06:00 to 06:00 the next day in America/Los_Angeles. Use Gold gaming_date.",
                "Hold is SUM(house_win_usd) divided by SUM(coin_in_usd), never an average of ratios. Theo means expected house win.",
                "Exclude off-floor rows. Machine-day queries require active and non-null location_id. Keep tracked play separate from floor meters.",
                "A payout anomaly is a lead to inspect, never wrongdoing. A negative house-win surprise means the house won less and guests were paid more than expected for the same wagers. For M-1158, say payouts were higher than expected. Expected net value is the estimated value of information after cost, not expected recovered cash. Do not target heavy losers.",
                "Use the trusted SQL for the example questions. The bottom-ten ranks are fixed for January through June. Describe LINEUP as reviewing the mix of games, LUCK as payout variation, and INSPECT as a check. Summarize verdict counts and show all ten rows. July decisions are a fixed 30-day snapshot.",
                "The walkway was closed on gaming dates March 3 through April 6 and reopened April 7. Compare entries per covered sensor hour. Describe the measured change only. Do not call it significant or claim that the closure caused the full decline.",
                "The May 1 schedule moved from 12.50 to 5.85 points per face-value dollar. The query shows observed full-week ratios, not those schedule values, and excludes the mixed week. In the answer, report both the schedule and the observed ratios. These are points spent to redeem rewards, never points earned or awarded.",
            ]}],
            "example_question_sqls":[{"id":key("sql", q),"question":[q],"sql":[sql]} for q,sql in QUESTIONS],
        }}
    spec["config"]["sample_questions"].sort(key=lambda q: q["id"])
    spec["instructions"]["example_question_sqls"].sort(key=lambda q: q["id"])
    payload = {"title":TITLE,"warehouse_id":WAREHOUSE,"serialized_space":json.dumps(spec),
               "description":"Workspace-only questions about the fictional casino's approved Gold figures."}
    command = ["update-space", existing["space_id"]] if existing else ["create-space"]
    result = json.loads(cli(PROFILE, "genie", *command, "--json", json.dumps(payload)) or "{}")
    print(result.get("space_id") or existing["space_id"])



if __name__ == "__main__":
    main()
